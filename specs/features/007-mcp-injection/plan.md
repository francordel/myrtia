# Plan 007 — MCP Injection Attacks

> How the spec will be built. Read `specs/constitution/` and `specs/features/007-mcp-injection/spec.md`
> first. Every part names the requirements it covers.

## Approach

Add a self-contained plugin module `backend/myrtia/plugins/mcp_injection.py` auto-discovered by
Myrtia's plugin registry without editing core orchestrator, connector, or UI files. For each
goal and selected MCP attack variant, the plugin presents simulated MCP server tool manifests
and runs a bounded JSON tool-calling loop over `target_connector.generate(messages)`. For the
`rug_pull` variant, the simulated MCP server mutates its tool description after turn 1 and emits
`mcp.manifest_mutated`. Forbidden MCP tool calls are flagged and graded via `judge_and_emit`.

## Affected areas

| Area | Change | Covers |
|---|---|---|
| `backend/myrtia/plugins/mcp_injection.py` | New plugin: 4 canonical MCP attack scenarios (`tool_poisoning`, `rug_pull`, `tool_shadowing`, `resource_output_injection`), simulated MCP server sandbox, manifest-mutation hook, forbidden-action detector, and `PluginSpec` registration (`"mcp-injection"`). | FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7 |
| `backend/tests/features/mcp_injection.feature` | Gherkin acceptance scenarios from `spec.md` (offline + `@e2e`). | FR-1, FR-2, FR-3, FR-4, FR-5 |
| `backend/tests/test_mcp_injection_bdd.py` | `pytest-bdd` step definitions driving `McpInjectionLive`. | FR-1, FR-2, FR-3, FR-4, FR-5 |
| `backend/tests/test_mcp_injection.py` | Unit tests for all 4 MCP families, canary-only data, rug-pull mutation, forbidden-action detection, variant filtering, `max_turns` cap, and connector error handling. | FR-2, FR-4, FR-5, FR-6, FR-7, NFR-1 |

## Data and state

- `McpToolDef(server, name, description, parameters_schema)`
- `McpScenario(id, family, benign_task, initial_tools, mutated_tools, simulated_responses, ...)`
- Result row additions: `goal`, `variant`, `mcp_family`, `tool_calls`, `forbidden_actions_triggered`, `response`, `score`, and `status`/`error` on connector failure.

## Contracts

- **Plugin ID:** `"mcp-injection"`
- **`config_schema`:** `JUDGE_SCHEMA` + `variants` (`text`, default `"all"`) + `max_turns` (`number`, default `4`)
- **Events emitted (`_emit`):**
  - `goal.started`, `mcp.manifest_loaded`, `mcp.manifest_mutated` (on rug pull), `mcp.tool_called`, `mcp.tool_responded`, `mcp.forbidden_action`, `target.responded`, `goal.finished`.

## Decisions

| Decision | Why | Alternative rejected |
|---|---|---|
| Self-contained prompt-level MCP tool-calling loop over `Connector.generate(messages)` | Works immediately on any Myrtia target model without blocking on `006-agent-targets` or editing `connectors/`. | Spawning external stdio/SSE MCP servers (requires external runtime and `006`). |
| In-memory deterministic MCP tool responses & canary data | Zero host side effects (NFR-1) and deterministic offline tests. | Live HTTP/filesystem calls. |

## Constitution check

- **Principles 1, 4, 5, 6, 8, 9, 10, 11, 12:** New plugin module only, spec-first, TDD, canary-only data, full structured event trace.

## Test strategy

| Requirement | Proof |
|---|---|
| FR-1, FR-2, FR-3 | `mcp_injection.feature` + `test_mcp_injection.py::test_canonical_mcp_scenarios_cover_four_families` |
| FR-4 | `mcp_injection.feature` (rug pull) + `test_mcp_injection.py::test_rug_pull_mutates_manifest_after_turn_one` |
| FR-5 | `mcp_injection.feature` + `test_mcp_injection.py::test_mcp_forbidden_action_detection` |
| FR-6, FR-7 | `test_mcp_injection.py::test_variant_filtering_and_max_turns_cap`, `test_connector_error_marks_failed` |

