# Tasks 002 — Agent Cards

- [x] **T1 — Write the UI acceptance scenarios** (FR-1, FR-2, FR-3, FR-4)
  Add `backend/tests_ui/features/agent_cards.feature` and `backend/tests_ui/test_agent_cards_ui.py`.
  Done when: scenarios are collected and fail in Playwright Chromium before UI changes.

- [x] **T2 — Implement agent card chips, quick-remove, and quick-add in `frontend/standalone.html`** (FR-1, FR-2, FR-3, FR-4, NFR-1)
  Add CSS tokens and update `renderGraph()` attacker nodes with `CARRIES` chips and `+ Tool` / `+ Priming` / `+ Agent` actions.
  Done when: `agent_cards.feature` and all existing `backend/tests_ui` scenarios pass.

- [x] **T3 — Validate and review** (FR-1 … FR-4, NFR-1, NFR-2)
  Run `ruff check backend`, `pytest -m "not e2e"`, `pytest backend/tests_ui`, and invoke `strict-frontend-customer` + `senior-code-reviewer` to audit.
  Done when: all checks are green and reviewers approve.

