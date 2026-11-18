# Tasks 007 — MCP Injection Attacks

> Small tasks (about 20–30 minutes each) in dependency order. Implement one at a time,
> test first: write the failing scenario or unit test, make it pass with the minimum
> code, refactor, run the checks, tick the box, stop.

- [x] **T1 — Write the acceptance scenarios** (FR-1, FR-2, FR-3, FR-4, FR-5)
  Add `backend/tests/features/mcp_injection.feature` from `spec.md`, with step definitions in `backend/tests/test_mcp_injection_bdd.py`.
  Done when: the offline scenarios are collected by `pytest` and fail because `"mcp-injection"` is not registered yet.

- [x] **T2 — Implement canonical MCP scenarios and simulated MCP sandbox** (FR-2, FR-3, FR-4, NFR-1)
  Write failing unit tests in `backend/tests/test_mcp_injection.py` for the 4 canonical MCP families (`tool_poisoning`, `rug_pull`, `tool_shadowing`, `resource_output_injection`), canary-only payloads, rug-pull manifest mutation, and `SimulatedMcpSandbox`, then implement them in `backend/myrtia/plugins/mcp_injection.py`.
  Done when: scenario and sandbox unit tests pass.

- [x] **T3 — Implement `McpInjectionLive` loop, forbidden-action detection, and plugin registration** (FR-1, FR-4, FR-5, FR-6, FR-7)
  Write failing unit tests in `backend/tests/test_mcp_injection.py` for forbidden-action detection, variant filtering, `max_turns` cap, connector error handling, and plugin registration; then implement `McpInjectionLive` and `register(PluginSpec(plugin_id="mcp-injection", ...))`.
  Done when: `ruff check backend` and `pytest -m "not e2e"` pass with zero warnings.

- [x] **T4 — Validate the spec** (FR-1 … FR-7, NFR-1, NFR-2)
  Walk `spec.md` requirement by requirement, state what test proves each one, and confirm `Definition of done`.
  Done when: every requirement is covered, all checks are green, and the supervisor approves.

- [x] **T5 — Render `mcp.*` events cleanly in the live UI** (FR-8)
  Add a UI scenario in `backend/tests_ui/features/agent_attacks.feature` (and `test_agent_attacks_ui.py`), see it fail, then update `evNode` in `frontend/standalone.html` to format `mcp.*` events with human-readable labels and warning styling for `mcp.forbidden_action` and `mcp.manifest_mutated`.
  Done when: `ruff check backend`, `pytest -m "not e2e"`, and `pytest backend/tests_ui` pass.
