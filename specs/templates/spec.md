# Spec NNN — <feature name>

> What and why. No stack, architecture or file names: those belong in `plan.md`.

- **Status:** Draft | Clarified | Implemented
- **Issue:** #<n>

## Context and goal

<Two or three sentences: the problem today and what changes for the user.>

## Users

- **<Primary user>** — <what they are trying to do>

## User stories

- **US-1** — As a <user>, I want <capability> so that <outcome>.

## Functional requirements

Numbered, in EARS notation (see `specs/README.md`). One behaviour per requirement.

- **FR-1** — WHEN <event>, THE SYSTEM SHALL <response>.
- **FR-2** — IF <condition>, THEN THE SYSTEM SHALL <response>.

## Non-functional requirements

- **NFR-1** — <performance, accessibility, security or compatibility constraint>

## Edge cases

- <Boundary or failure situation and the expected behaviour>

## Out of scope

- <What this feature deliberately does not do>

## Acceptance scenarios

Gherkin scenarios that prove the requirements. They become a `.feature` file run by
`pytest-bdd`; tag the ones that need a live model with `@e2e`.

```gherkin
Scenario: <observable outcome>            # covers FR-1
  Given <starting state>
  When <action>
  Then <expected result>
```

Manual checks (only for behaviour no automated scenario can reach):

- <What to do and what must be seen> (covers FR-2)

## Definition of done

1. Every acceptance scenario passes, and each was seen failing before the code existed.
2. `ruff check backend`, `pytest -m "not e2e"` and the feature's `e2e` scenarios pass.

## Open questions

- [NEEDS CLARIFICATION] <question that must be answered before planning>
