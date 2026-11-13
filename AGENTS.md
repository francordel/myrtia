# AGENTS.md — Myrtia

Myrtia is a red-teaming workbench for LLMs and AI agents: one web UI that runs attacks
from several backends as plugins (classic single-turn, multi-turn and multi-agent),
lets the operator design new multi-agent attacks, tests defences, and traces every step
live. It is dual-use security tooling for authorised testing only (see `DUAL_USE.md`).

## Stack

- Backend: Python 3.11+ (uv installs 3.12), FastAPI, WebSocket event stream, SQLite.
- Frontend: one zero-build file, `frontend/standalone.html` (no bundler, no framework).
- Attacks: plugins in `backend/myrtia/plugins/`, including adapters for ARES, garak and
  PyRIT. The council attack is vendored in `backend/vendor/ares-council` (Apache-2.0).

## Commands

- Run: `uv run myrtia --reload` (API + UI at http://127.0.0.1:8000/)
- Tests: `uv run --extra dev pytest -m "not e2e"` (offline tier; must stay green)
- End-to-end: `uv run --extra dev pytest -m e2e` (Gherkin scenarios against a live local model)
- UI scenarios: `uv run --group ui pytest backend/tests_ui` (real browser, simulated model;
  once: `uv run --group ui playwright install chromium`)
- Lint: `uv run --extra dev ruff check backend` (zero warnings)

## Structure

- `backend/myrtia/` — `api/`, `orchestrator/`, `plugins/` (attacks, auto-discovered),
  `connectors/` (targets), `judges/`, `events/`, `hitl/`, `store/`
- `backend/tests/` — pytest suite (`features/` holds the behaviour-driven tests)
- `backend/tests_ui/` — UI scenarios run in a browser (`features/`, steps, simulated model)
- `frontend/standalone.html` — the whole UI
- `specs/` — constitution, feature specs and templates (start at `specs/README.md`)
- `docs/` — architecture and design notes; `docs/audit-log.md` is the historical findings log

## Workflow: spec-driven development

1. Read `specs/constitution/` and the active feature folder before touching code.
2. No behaviour change without a spec: `spec.md` (what, why) → `plan.md` (how) →
   `tasks.md` (small steps). Use the templates in `specs/templates/`.
3. Plan first and wait for approval before editing files.
4. Implement one task at a time with test-driven development (see Testing), then stop.
5. When code and spec disagree, update the spec in the same change.

## Testing: TDD and behaviour-driven scenarios

- Test first, always: write the failing test, run it and see it fail, write the minimum
  code that makes it pass, then refactor with the tests green. No production code
  without a test that asked for it.
- Acceptance criteria are Gherkin scenarios (Given / When / Then) in
  `backend/tests/features/*.feature`, bound to step functions with `pytest-bdd`.
  Write the scenario from the spec before the code.
- Scenarios that need a live model endpoint are end-to-end tests: mark them `e2e`. They
  run with `uv run --extra dev pytest -m e2e` against a local model.
- UI behaviour is tested the same way: write the scenario in
  `backend/tests_ui/features/*.feature` first and see it fail in the browser tier.
- Unit tests cover the logic underneath the scenarios; both tiers must pass before a
  task is done.

## Conventions

- Everything in the repo is written in English: code, comments, specs, docs, commits.
- Attacks and connectors are added as new modules; do not edit registries or core code
  to add one (see `CONTRIBUTING.md`).
- Surgical changes: touch only what the task needs and keep existing comments.
- No sugar-coating in reviews: state defects plainly, with evidence from a real run.

## Do not

- Do not modify the attack logic in `backend/vendor/ares-council` (paper reproducibility).
- Do not add a build step, bundler or framework to the frontend.
- Do not log, store or stream secrets (API keys, bearer headers) unredacted.
- Do not weaken the SSRF guards on connectors and proxies, or follow redirects.
- Do not commit `.env*`, `*.private.*` files or worked harmful completions.
- Do not commit or push unless the maintainer asks, and add no tool attribution lines.

## Before finishing any task

- Run the lint and test commands above and report the real output.
- For UI changes, run the UI scenarios and add one for the new behaviour.
- List the requirement ids (`FR-n`) the change covers and tick the task in `tasks.md`.
