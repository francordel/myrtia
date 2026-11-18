Feature: Canvas Preview
  As a red-team operator
  I want to test the current graph against one goal from a panel docked on the canvas
  So that I can see the active agent highlighted and inspect results without leaving the builder

  Scenario: Docked preview runs one goal without leaving the builder
    Given the Myrtia console is open
    And every agent uses the simulated model
    When I open the canvas preview and run with goal "Say hello"
    Then the graph builder stays visible
    And the docked preview panel shows the target response and judge score
    And no node remains highlighted after the preview finishes

  Scenario: Active node is highlighted during preview events
    Given the Myrtia console is open
    When a preview event arrives for "target.responded"
    Then the target node on the canvas is highlighted as active

  Scenario: Stopping or closing preview clears node highlights and errors render in log
    Given the Myrtia console is open
    When a preview event arrives for "target.responded"
    And I close the canvas preview panel
    Then no node remains highlighted after the preview finishes
    When a preview failure event is received
    Then the docked preview panel shows the error message

