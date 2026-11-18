# Spec 003 — Canvas Preview

- **Status:** Implemented
- **Issue:** #<tbd>

## Context and goal

When designing multi-agent topologies on the graph canvas, operators currently have to click "Launch attack", leave the builder for the live run view, and switch back to iterate.

This feature adds a docked preview panel directly on the graph builder so operators can test the current graph against one goal, watch the active agent node highlight live on the canvas as events arrive, and inspect the result without leaving the builder.

## Users

- **Red-team operator** — wants to test a topology against a single goal and see which agent is acting on the canvas while iterating.

## User stories

- **US-1** — As a red-team operator, I want to run a quick single-goal preview from a panel docked on the canvas so that I can verify my topology without leaving the builder.
- **US-2** — As a red-team operator, I want the active node on the canvas to highlight as events stream during the preview so that I can follow the execution flow visually.

## Functional requirements

- **FR-1** — THE SYSTEM SHALL provide a docked preview panel on the graph builder (`#gPreviewPanel`) with a `Preview` trigger button (`#gPreviewBtn`), a goal input, and a live output log (`#gPreviewLog`), keeping the operator on the builder view.
- **FR-2** — WHEN the operator starts a preview, THE SYSTEM SHALL submit a single-goal run of the current graph (`POST /runs`), stream its events over WebSocket (with status polling fallback), and display each step inside the docked panel.
- **FR-3** — WHILE a preview run is active, THE SYSTEM SHALL highlight the currently acting node on `#gcanvas` (`.gnode.is-active`) as events arrive (`proposal.created`/`agent.message` -> attacker, `chairman.synthesized` -> chairman, `target.responded` -> target, `judge.scored` -> evaluator) and clear all highlights when finished.
- **FR-4** — WHEN the operator stops or closes the docked preview panel during an active preview, THE SYSTEM SHALL cancel the preview run (`POST /runs/{id}/stop`), close its stream, and clear node highlights.
- **FR-5** — IF the preview fails to launch or returns an error event, THEN THE SYSTEM SHALL display the error inside `#gPreviewLog` and restore the preview button without navigating away.

## Non-functional requirements

- **NFR-1** — Panel and active-node highlight styling shall use existing CSS design tokens and work in both dark and light themes.
- **NFR-2** — Existing Playwright UI scenarios (`builder.feature`, `harness.feature`) shall remain green.

## Edge cases

- Goal input is blank when clicking Preview (falls back to `#gGoal` or prompts for a goal without crashing).
- Preview is closed while still running (cancels run and cleans up WebSocket/timers).
- Model endpoint is unreachable (shows clear error inside the docked panel).

## Out of scope

- Multi-goal batch runs from the preview panel (use `Launch attack` for full campaigns).

## Acceptance scenarios

```gherkin
Scenario: Docked preview runs one goal without leaving the builder  # covers FR-1, FR-2, FR-3
  Given the Myrtia console is open
  And every agent uses the simulated model
  When I open the canvas preview and run with goal "Say hello"
  Then the graph builder stays visible
  And the docked preview panel shows the target response and judge score
  And no node remains highlighted after the preview finishes

Scenario: Active node is highlighted during preview events  # covers FR-3
  Given the Myrtia console is open
  When a preview event arrives for "target.responded"
  Then the target node on the canvas is highlighted as active

@e2e
Scenario: Canvas preview runs against a live local model  # covers FR-1, FR-2, FR-3
  Given a live local model endpoint is running
  When the operator runs a canvas preview against the live model
  Then the docked preview panel completes with a live response
```

## Definition of done

1. Every acceptance scenario passes in Playwright Chromium (`pytest backend/tests_ui`), and each was seen failing before the code existed.
2. `ruff check backend`, `pytest -m "not e2e"`, and live `@e2e` preview test pass.
3. No regressions in existing `builder.feature` scenarios.

