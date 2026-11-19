# Spec 012 — X-Teaming run-mode tab

> What and why. No stack, architecture or file names: those belong in `plan.md`.

- **Status:** Implemented
- **Issue:** —

## Context and goal

X-Teaming (spec 010) is Myrtia's flagship multi-agent attack, but in the console it is
buried as one entry in the Standard tab's attack dropdown. Operators looking at the
"agentic" area (the graph builder and its topologies) expect the multi-agent attack to be
there. This feature gives X-Teaming its own run-mode tab, next to the agentic graph
builder, so it is discoverable and one click to configure and launch.

## Users

- **Operator** — wants to reach and launch X-Teaming directly from the top-level run
  modes, not by hunting through the attack dropdown.

## User stories

- **US-1** — As an operator, I want an "X-Teaming" tab beside "Agentic · graph builder"
  so that the multi-agent attack is front and centre.
- **US-2** — As an operator, I want that tab to open X-Teaming ready to configure and
  launch, with its own settings, not the graph canvas.

## Functional requirements

- **FR-1** — THE console SHALL show a third run-mode tab, "X-Teaming", in the run-mode
  tab row, between "Agentic · graph builder" and "Standard".
- **FR-2** — WHEN the operator selects the X-Teaming tab, THE console SHALL set the active
  attack to the `xteaming` plugin and show that plugin's description and configuration.
- **FR-3** — WHILE the X-Teaming tab is active, THE console SHALL hide the graph canvas and
  SHALL hide the attack-plugin selector (the attack is fixed to `xteaming`).
- **FR-4** — WHEN the operator launches from the X-Teaming tab, THE console SHALL start a
  run of the `xteaming` plugin with the configured settings.
- **FR-5** — THE X-Teaming tab SHALL NOT change the backend, the `xteaming` plugin or the
  graph builder; it is a presentation entry point only.

## Non-functional requirements

- **NFR-1** — Zero-build frontend: the change stays within `frontend/standalone.html`.
- **NFR-2** — Selecting the Agentic or Standard tab continues to work exactly as before.

## Edge cases

- Reloading with the X-Teaming tab remembered restores it with `xteaming` selected.
- Switching from X-Teaming to Standard leaves `xteaming` selected but shows the selector
  again, so the operator can change the attack.

## Out of scope

- Any change to the X-Teaming algorithm, prompts or defaults (spec 010).
- Rendering X-Teaming's four roles on the graph canvas (it is not a canvas topology).

## Acceptance scenarios

In `backend/tests_ui/features/xteaming_tab.feature` (browser tier):

```gherkin
Scenario: The X-Teaming tab selects the plugin            # FR-1, FR-2, FR-3
  Given the Myrtia console is open
  When I open the X-Teaming run mode
  Then the attack is set to "xteaming"
  And its description is shown
  And the attack-plugin selector is hidden
  And the graph canvas is hidden
```

## Definition of done

1. The acceptance scenario passes in the UI tier, seen failing before the code existed.
2. The agentic and standard tabs still behave as before.

## Open questions

None.
