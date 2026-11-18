# Tasks 003 — Canvas Preview

- [x] **T1 — Write the UI acceptance scenarios** (FR-1, FR-2, FR-3)
  Add `backend/tests_ui/features/canvas_preview.feature` and `backend/tests_ui/test_canvas_preview_ui.py`.
  Done when: scenarios are collected and fail in Playwright Chromium before UI changes.

- [x] **T2 — Implement docked preview panel and active-node highlighting in `frontend/standalone.html`** (FR-1, FR-2, FR-3, FR-4, FR-5, NFR-1)
  Add `.gnode.is-active` / `#gPreviewPanel` CSS + HTML + `startCanvasPreview` / `stopCanvasPreview` / `gHighlightForEvent`.
  Done when: `canvas_preview.feature` and all existing `backend/tests_ui` scenarios pass.

- [x] **T3 — Validate against live local model and strict reviewers** (FR-1 … FR-5, NFR-1, NFR-2)
  Run `ruff check backend`, `pytest -m "not e2e"`, `pytest backend/tests_ui`, a live `@e2e` canvas-preview run against `Qwen/Qwen2.5-1.5B-Instruct`, and invoke `strict-frontend-customer` + `senior-code-reviewer`.
  Done when: all checks are green and reviewers approve.

