# Plan 006 — Agent Targets

> How the spec will be built. Read `specs/constitution/` and `specs/features/006-agent-targets/spec.md`
> first. Every part names the requirements it covers.

## Approach

Add a new connector module `backend/myrtia/connectors/agent_target.py` implementing
`AgentTargetConnector` (conforming to `Connector`), registered in
`backend/myrtia/connectors/factory.py` under `"agent_sdk"`. The connector ships a built-in
in-memory sandbox agent (`SandboxAgentRuntime`) with safe simulated tools (`read_note`,
`write_note`, `lookup_customer`, `send_external_message`, `admin_export`) and a specialist handoff target
(`compliance-reviewer`), plus an optional `openai-agents` SDK bridge when `agents` is
installed. Every tool call, tool response, handoff, and forbidden action is emitted via an
optional `set_event_emitter` hook and recorded on `last_trace`.

## Affected areas

| Area | Change | Covers |
|---|---|---|
| `backend/myrtia/connectors/agent_target.py` | New `AgentTargetConnector`, `SandboxAgentRuntime`, forbidden-action rules, event emission, and optional `openai-agents` adapter. | FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7 |
| `backend/myrtia/connectors/factory.py` | Register `"agent_sdk"` kind in `_KINDS` and `build_target_connector` (after SSRF check). | FR-1, FR-5 |
| `backend/tests/features/agent_targets.feature` | Gherkin acceptance scenarios from `spec.md` (offline + `@e2e`). | FR-1, FR-2, FR-3, FR-4, FR-5 |
| `backend/tests/test_agent_targets_bdd.py` | `pytest-bdd` step definitions for `agent_targets.feature`. | FR-1, FR-2, FR-3, FR-4, FR-5 |
| `backend/tests/test_agent_targets.py` | Unit tests for tool calls, handoffs, forbidden actions, max-turn cap, SSRF rejection, and error handling. | FR-1..FR-7, NFR-1, NFR-2 |

## Contracts

- **Connector kind:** `"agent_sdk"` in `build_target_connector(spec)`
- **Events emitted (`set_event_emitter`):**
  - `agent.tool_called` (`agent`, `step`, `tool`, `arguments`, `forbidden`)
  - `agent.tool_responded` (`agent`, `step`, `tool`, `response`)
  - `agent.handoff` (`from_agent`, `to_agent`, `reason`)
  - `agent.forbidden_action` (`agent`, `tool`, `reason`)
- **Result metadata on `AgentTargetConnector`:** `last_trace` (`tool_calls`, `handoffs`, `forbidden_actions`, `attack_succeeded`).

## Decisions

| Decision | Why | Alternative rejected |
|---|---|---|
| Built-in pure-Python `SandboxAgentRuntime` + optional `openai-agents` bridge | Works out of the box with zero mandatory new PyPI dependencies (`NFR-2`) while supporting `openai-agents` when installed (`FR-7`). | Hard-requiring `openai-agents` in core dependencies (would break offline/airgapped installs). |
| Conform to `Connector.generate(prompt)` | Any existing Myrtia attack (`direct`, `crescendo`, `council`, `graph`, etc.) can target an agent immediately without rewriting attacks. | Creating a separate incompatible target interface. |

## Constitution check

- **Principles 4, 5, 6, 7, 11, 12:** Additive connector module, SSRF guard enforced before construction, no unredacted secrets, TDD with `pytest-bdd`, full structured event trace.

