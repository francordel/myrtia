# Spec 001 — Automated behaviour scenarios for the web UI

> What and why. No stack, architecture or file names: those belong in `plan.md`.

- **Status:** Implemented (pending the first pull-request run, FR-14 and FR-15)
- **Issue:** to be created

## Context and goal

Myrtia's behaviour-driven tests cover the backend only. The web UI, where most upcoming
features live, has no automated test: every change to the canvas or the live view is
checked by hand, and regressions in it have reached users before.

The project rule is test first, with acceptance criteria written as Gherkin scenarios.
That rule cannot be followed for the UI until a scenario can open the page, act on it
and check what is shown. This feature makes that possible and protects the current
canvas with a first set of scenarios, so the next features can be built test first.

## Users

- **Contributor** — writes a UI scenario before changing the UI, runs it, and sees it
  fail and then pass.
- **Maintainer / reviewer** — trusts that a pull request did not break the canvas or
  the live view, because the scenarios ran on it.

## User stories

- **US-1** — As a contributor, I want to describe UI behaviour as a Given/When/Then
  scenario and have it executed in a real browser, so that I can work test first on the
  UI.
- **US-2** — As a contributor, I want the UI scenarios to run on my machine with no
  model server and no API key, so that I can run them at any time.
- **US-3** — As a contributor, I want a failing scenario to show me what the page
  looked like, so that I can find the cause quickly.
- **US-4** — As a maintainer, I want the UI scenarios to run on every pull request and
  block the merge when they fail, so that regressions do not reach `main`.
- **US-5** — As a maintainer, I want the canvas behaviours that exist today to be
  covered, so that the upcoming canvas work starts from a protected baseline.

## Functional requirements

### Running scenarios

- **FR-1** — THE SYSTEM SHALL execute UI scenarios written in the same Given/When/Then
  language and by the same test runner as the existing backend scenarios.
- **FR-2** — WHEN the UI scenarios start, THE SYSTEM SHALL launch its own instance of
  the application, on a free local port and with an empty, temporary data store.
- **FR-3** — WHEN the UI scenarios finish, THE SYSTEM SHALL stop every process it
  started and delete the temporary data it created.
- **FR-4** — THE SYSTEM SHALL NOT read or modify the operator's own run history,
  settings or stored keys while running UI scenarios.
- **FR-5** — THE SYSTEM SHALL let a developer run the UI scenarios on their own, and
  run the existing offline scenarios without them, each with one documented command.
- **FR-6** — WHERE a developer asks for a visible browser, THE SYSTEM SHALL run the
  scenarios in a visible browser window instead of a hidden one.

### Simulated model

- **FR-7** — THE SYSTEM SHALL provide a simulated model endpoint that the application
  can use as attacker, target and judge, and that returns fixed, repeatable replies.
- **FR-8** — WHILE UI scenarios run, THE SYSTEM SHALL block every network request to a
  host other than the local machine, and the scenarios SHALL pass with those requests
  blocked.
- **FR-9** — IF the simulated model receives a request it has no specific reply for,
  THEN THE SYSTEM SHALL answer with a fixed default reply instead of failing.

### Failures

- **FR-10** — WHEN a UI scenario fails, THE SYSTEM SHALL save a screenshot of the page
  and the browser's error messages for that scenario.
- **FR-11** — IF the page raises an unhandled script error during a scenario, THEN THE
  SYSTEM SHALL fail that scenario and report the error.
- **FR-12** — IF the browser needed by the scenarios is not installed, THEN THE SYSTEM
  SHALL fail with a message that states the command to install it, instead of skipping.
- **FR-13** — IF the application instance does not become ready, THEN THE SYSTEM SHALL
  fail with a message that includes the application's startup output.

### Continuous integration

- **FR-14** — WHEN a pull request to `main` is opened or updated, THE SYSTEM SHALL run
  the UI scenarios and report a failing check if any scenario fails.
- **FR-15** — WHEN a UI scenario fails in continuous integration, THE SYSTEM SHALL
  attach the saved screenshots and error messages to the run so they can be downloaded.

### Baseline scenarios

- **FR-16** — THE SYSTEM SHALL include scenarios covering these existing behaviours:
  1. the page loads and the graph builder is shown with its default agents;
  2. adding an attacker adds an agent node to the canvas;
  3. removing an attacker removes its node from the canvas;
  4. editing an agent's model changes what its node shows;
  5. choosing another topology changes the canvas to that topology's agents;
  6. launching a run from the builder with one goal shows the target's response and the
     judge's score, and the run ends as finished.

## Non-functional requirements

- **NFR-1** — The UI scenarios complete in under two minutes on a developer laptop.
- **NFR-2** — The scenarios are deterministic: twenty consecutive runs give twenty
  passes.
- **NFR-3** — Scenarios run in one browser engine, at one desktop window size.
- **NFR-4** — The UI stays a single file served as-is: nothing in this feature adds a
  build step to the frontend or changes what is shipped to users.
- **NFR-5** — Everything needed to run the scenarios is installed by documented
  commands, and none of it is installed for users who only run Myrtia.

## Edge cases

- The usual application port is already in use: the scenarios still run (FR-2).
- A previous run was interrupted and left a process behind: the next run is not
  affected by it.
- A scenario fails midway through a run: the run and the processes are still cleaned up
  (FR-3).
- The page asks an external host for a resource it can work without (for example web
  fonts): the request is blocked and the scenario is unaffected (FR-8).
- The machine has no internet connection: the scenarios still pass (FR-8).
- The developer has their own Myrtia open with stored keys and history: nothing in it
  changes (FR-4).

## Out of scope

- More than one browser engine, and narrow or mobile window sizes.
- Comparing screenshots pixel by pixel (visual regression).
- Scenarios for the History, Statistics and Plugins views.
- UI scenarios against a real model server.
- Load or performance testing of the UI.

## Acceptance scenarios

The baseline scenarios (FR-16), as they will be written:

```gherkin
Feature: Graph builder

  Scenario: The builder opens with its default agents            # FR-16.1
    Given the Myrtia console is open
    Then the graph builder is shown
    And the canvas shows 3 attacker nodes
    And the canvas shows a target node
    And the canvas shows an evaluator node

  Scenario: Adding an attacker adds a node                        # FR-16.2
    Given the Myrtia console is open
    When I add an attacker
    Then the canvas shows 4 attacker nodes

  Scenario: Removing an attacker removes its node                 # FR-16.3
    Given the Myrtia console is open
    And I have added an attacker
    When I remove the last attacker
    Then the canvas shows 3 attacker nodes

  Scenario: Editing an agent's model updates its node             # FR-16.4
    Given the Myrtia console is open
    When I set the model of attacker 1 to "test-model"
    Then the node of attacker 1 shows "test-model"

  Scenario: Choosing a topology changes the canvas                # FR-16.5
    Given the Myrtia console is open
    When I choose the "Chairman" topology
    Then the canvas shows a chairman node

  Scenario: A run launched from the builder is shown live         # FR-16.6
    Given the Myrtia console is open
    And every agent uses the simulated model
    When I launch a run with the goal "Say hello"
    Then the live view shows a target response
    And the live view shows a judge score
    And the run ends as finished
```

Behaviour of the test system itself, proven by its own tests:

```gherkin
Feature: The UI scenarios are isolated and leave evidence

  Scenario: The operator's data is untouched                      # FR-2, FR-4
    Given the operator's run history as it was before the scenarios started
    When a run is launched in the private instance
    Then the private instance has stored that run
    And the operator's run history is unchanged

  Scenario: Nothing leaves the machine                            # FR-8
    Given the Myrtia console is open
    When the browser requests a page from an external host
    Then the request is blocked
    And the graph builder is shown

  Scenario: A failing scenario leaves evidence                    # FR-10
    Given a UI scenario that fails
    When it finishes
    Then a screenshot and the browser's messages are saved for it

  Scenario: A script error fails the scenario                     # FR-10, FR-11
    Given a UI scenario whose page raises an unhandled script error
    When it finishes
    Then the scenario is reported as failed with that error
    And a screenshot and the browser's messages are saved for it
```

Manual checks:

- Open a pull request that breaks one baseline behaviour and confirm the check fails
  and the screenshot can be downloaded (FR-14, FR-15).
- Run the scenarios with the visible-browser option and confirm a window appears (FR-6).

## Definition of done

1. Every acceptance scenario passes, and each was seen failing before the code existed.
2. `ruff check backend` and `pytest -m "not e2e"` pass, and the UI scenarios pass
   locally and in continuous integration.
3. The contributor documentation states how to install what is needed and how to run
   the UI scenarios.

## Decisions from clarification

- Scenarios may rely on small, stable identifiers added to the UI markup, limited to
  attributes that do not change how the page looks or behaves.
- The existing offline command (`pytest -m "not e2e"`) stays as it is and needs no
  browser; the UI scenarios have their own command (FR-5).
- Scope is the six baseline scenarios; a simulated model is used for full runs; the
  scenarios run on every pull request and block the merge.

## Decisions from implementation

- Scenarios act as a returning operator: the first-visit welcome offer is marked as
  already seen, because it covers the canvas and is not what the scenarios test.
- No identifier had to be added to the UI markup: the existing element ids and data
  attributes were enough. The page is unchanged by this feature.
- The fixed reply of the simulated model is accepted by every role of the default
  topology, so it has no request-specific rules.

## Open questions

None.
