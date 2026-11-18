# Plan 002 — Agent Cards

> How the spec will be built. Read `specs/constitution/` and `specs/features/002-agent-cards/spec.md` first.

## Approach

Enhance `renderGraph()` in `frontend/standalone.html` so attacker nodes render a compact
`CARRIES` section below `.gm` / `.gp` containing chips for prompt (`Default prompt` /
`Custom prompt` + `×`), tools (`<tool>` + `×`), and contextual priming (`Few-shot priming` + `×`),
plus a compact action bar (`+ Tool`, `+ Priming`, `+ Agent`). Pointer/click handlers on chip
remove buttons and card quick-actions call `ev.stopPropagation()` so they never trigger node
dragging or `#gdialog`.

## Affected areas

| Area | Change | Covers |
|---|---|---|
| `frontend/standalone.html` | CSS for `.gc-carries`, `.gc-chip`, `.gc-acts` (using theme tokens); `renderGraph()` attacker card markup + click/pointer handlers. | FR-1, FR-2, FR-3, FR-4, NFR-1 |
| `backend/tests_ui/features/agent_cards.feature` | Gherkin UI scenarios from `spec.md`. | FR-1, FR-2, FR-3, FR-4 |
| `backend/tests_ui/test_agent_cards_ui.py` | Playwright Chromium step definitions for `agent_cards.feature`. | FR-1, FR-2, FR-3, FR-4, NFR-2 |

## Decisions

| Decision | Why | Alternative rejected |
|---|---|---|
| Render chips inside existing `.gnode.attacker` keeping `.gr`, `.gm`, `.gx`, `.gport` | Preserves 100% compatibility with existing `test_builder.py` selectors and drag/edge wiring. | Replacing `.gnode` with a brand-new DOM structure (would break existing UI tests and edge anchors). |

## Test strategy

| Requirement | Proof |
|---|---|
| FR-1, FR-2, FR-3, FR-4 | `backend/tests_ui/features/agent_cards.feature` run via Playwright Chromium |
| NFR-2 | Full `pytest backend/tests_ui`, `ruff check backend`, and `pytest -m "not e2e"` |

