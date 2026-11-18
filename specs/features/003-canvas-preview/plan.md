# Plan 003 — Canvas Preview

> How the spec will be built. Read `specs/constitution/` and `specs/features/003-canvas-preview/spec.md` first.

## Approach

Add a docked preview bar/panel (`#gPreviewPanel`) inside `#agenticPane` in
`frontend/standalone.html` plus a `Preview` button (`#gPreviewBtn`) in `.gbottom`. Clicking
Preview builds a 1-goal payload from `graphBody(false)` (capped to the preview goal), posts to
`POST /runs`, opens a WebSocket to `/ws/runs/{id}` (plus lightweight polling fallback),
highlights the active `.gnode` with `.is-active` using `gHighlightForEvent(ev)`, and renders
compact step entries inside `#gPreviewLog` without calling `openRun()`.

## Affected areas

| Area | Change | Covers |
|---|---|---|
| `frontend/standalone.html` | CSS for `.gnode.is-active` and `#gPreviewPanel`; HTML for `#gPreviewBtn` & `#gPreviewPanel`; JS functions `gHighlightForEvent`, `startCanvasPreview`, `stopCanvasPreview`. | FR-1, FR-2, FR-3, FR-4, FR-5, NFR-1 |
| `backend/tests_ui/features/canvas_preview.feature` | Gherkin UI scenarios from `spec.md`. | FR-1, FR-2, FR-3 |
| `backend/tests_ui/test_canvas_preview_ui.py` | Playwright Chromium step definitions (simulated model + live local model `@e2e`). | FR-1, FR-2, FR-3, NFR-2 |

## Test strategy

| Requirement | Proof |
|---|---|
| FR-1, FR-2, FR-3, FR-4, FR-5 | `backend/tests_ui/features/canvas_preview.feature` in Playwright Chromium |
| Live model verification | `@e2e` test running `startCanvasPreview` against live local `Qwen/Qwen2.5-1.5B-Instruct` |

