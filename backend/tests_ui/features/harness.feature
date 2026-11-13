Feature: The UI scenarios are isolated and leave evidence
  As a contributor
  I want the UI scenarios to be safe to run and easy to debug
  So that I can trust them on my machine and on every pull request

  Scenario: The operator's data is untouched
    Given the operator's run history as it was before the scenarios started
    When a run is launched in the private instance
    Then the private instance has stored that run
    And the operator's run history is unchanged

  Scenario: Nothing leaves the machine
    Given the Myrtia console is open
    When the browser requests a page from an external host
    Then the request is blocked
    And the graph builder is shown

  Scenario: A failing scenario leaves evidence
    Given a UI scenario that fails
    When it finishes
    Then a screenshot and the browser's messages are saved for it

  Scenario: A script error fails the scenario
    Given a UI scenario whose page raises an unhandled script error
    When it finishes
    Then the scenario is reported as failed with that error
    And a screenshot and the browser's messages are saved for it
