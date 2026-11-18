# Spec 002 — Agent Cards

- **Status:** Implemented
- **Issue:** #<tbd>

## Context and goal

In the graph builder, attacker nodes currently show only a single text line for the model and a truncated line for the prompt, hiding which tools or contextual priming each agent carries until the operator opens the edit modal.

This feature turns each attacker node on the canvas into a structured agent card that displays what the agent carries (name/role, description, prompt, tools, priming) and lets the operator add or remove those parts—and add a new attacker agent—directly from the node.

## Users

- **Red-team operator** — wants to inspect at a glance what each attacker agent carries and quickly add/remove tools, priming, custom prompts, or additional attackers on the canvas.

## User stories

- **US-1** — As a red-team operator, I want each attacker node on the canvas to show its prompt status, tools, and priming chips so that I can audit the attack setup without opening every modal.
- **US-2** — As a red-team operator, I want to add or remove tools, priming, custom prompts, or a new attacker directly from an agent card so that I can iterate rapidly on topologies.

## Functional requirements

- **FR-1** — THE SYSTEM SHALL display on each attacker node a `CARRIES` section showing: prompt status (`Default prompt` or `Custom prompt`), each granted tool as a chip, and active contextual priming as a badge, along with the agent's role/name, model, and optional description.
- **FR-2** — WHEN the operator clicks the remove (`×`) button on a custom prompt, tool chip, or priming badge on an agent card, THE SYSTEM SHALL remove that item from the agent's configuration and update the node immediately without opening the edit dialog.
- **FR-3** — WHEN the operator clicks the quick-add (`+ Tool`, `+ Priming`, or `+ Agent`) controls on an agent card, THE SYSTEM SHALL open the tool picker for that agent, enable contextual priming, or add a new attacker node directly on the canvas.
- **FR-4** — THE SYSTEM SHALL preserve all existing node behaviors (opening the edit dialog on `.gr`/node click, removing an attacker via `.gx`, node dragging, and `.gport` edge wiring) across both dark and light themes.

## Non-functional requirements

- **NFR-1** — All card styling shall use existing CSS design tokens in `frontend/standalone.html` and maintain legible contrast in both dark and light themes.
- **NFR-2** — Existing Playwright UI scenarios (`builder.feature`, `harness.feature`) shall remain green.

## Edge cases

- An agent has no tools and default prompt (shows `Default prompt` with no tool chips and no broken layout).
- Removing the last tool or clearing a custom prompt updates `GS` and persists in `localStorage`.
- Clicking a chip's `×` or quick-add button does not trigger node drag or open `#gdialog`.

## Out of scope

- Modifying backend attack execution logic (existing `GS.attackers` serialization already supports `system`, `tools`, and `priming`).

## Acceptance scenarios

```gherkin
Scenario: Agent card displays prompt, tools, and priming chips  # covers FR-1
  Given the Myrtia console is open
  When attacker 1 has a custom prompt, a tool, and contextual priming configured
  Then the node of attacker 1 shows "Custom prompt", the tool chip, and "Few-shot priming"

Scenario: Removing a tool or priming chip from an agent card updates the node  # covers FR-2
  Given the Myrtia console is open
  And attacker 1 has a tool and contextual priming configured
  When I remove the tool chip from attacker 1's card
  And I remove the priming chip from attacker 1's card
  Then the node of attacker 1 no longer shows that tool or "Few-shot priming"

Scenario: Adding a tool and a new attacker directly from an agent card  # covers FR-3, FR-4
  Given the Myrtia console is open
  When I click "+ Agent" on attacker 1's card
  Then the canvas shows 4 attacker nodes
```

## Definition of done

1. Every acceptance scenario passes in Playwright Chromium (`pytest backend/tests_ui`), and each was seen failing before the code existed.
2. `ruff check backend` and `pytest -m "not e2e"` pass.
3. No regressions in existing `builder.feature` scenarios.

