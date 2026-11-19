# Tasks 006 — Agent Targets

> Small tasks (about 20–30 minutes each) in dependency order. Implement one at a time,
> test first: write the failing scenario or unit test, make it pass with the minimum
> code, refactor, run the checks, tick the box, stop.

- [x] **T1 — Write the acceptance scenarios** (FR-1, FR-2, FR-3, FR-4, FR-5)
  Add `backend/tests/features/agent_targets.feature` and `backend/tests/test_agent_targets_bdd.py`.
  Done when: the offline scenarios are collected by `pytest` and fail because `"agent_sdk"` / `agent_target.py` does not exist yet.

- [x] **T2 — Implement `SandboxAgentRuntime`, forbidden-action rules, and `AgentTargetConnector`** (FR-1, FR-2, FR-3, FR-4, FR-6, FR-7, NFR-1, NFR-2)
  Write failing unit tests in `backend/tests/test_agent_targets.py`, then implement `backend/myrtia/connectors/agent_target.py`.
  Done when: all `agent_target.py` unit tests pass.

- [x] **T3 — Wire `"agent_sdk"` into `connectors/factory.py` with SSRF guard** (FR-1, FR-5)
  Write failing factory/SSRF unit tests in `backend/tests/test_agent_targets.py`, then add `"agent_sdk"` to `backend/myrtia/connectors/factory.py`.
  Done when: `ruff check backend`, `pytest -m "not e2e"`, and `pytest backend/tests_ui` pass.

- [x] **T4 — Validate the spec** (FR-1 … FR-7, NFR-1, NFR-2)
  Run all 4 verification tiers (including `@e2e` against a live local model) and have `sdd-supervisor` review.
  Done when: every requirement is covered and `sdd-supervisor` approves.
