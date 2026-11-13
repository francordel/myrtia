Feature: From the console to the dashboard
  As an operator
  I want one click from the console to the observability dashboard
  So that I do not have to remember its address (spec 008)

  Scenario: The Dashboard control opens the dashboard
    Given the Myrtia console is open
    And the dashboard is running
    When I press the Dashboard control
    Then the dashboard opens in a new tab
    And the console is still on the graph builder

  Scenario: The Dashboard control explains how to start it
    Given the Myrtia console is open
    And the dashboard is not running
    When I press the Dashboard control
    Then a dialog says the dashboard is not running
    And the dialog shows the command that starts it
    And the dialog offers to open the dashboard anyway
    When I close the dialog
    Then the console is still on the graph builder
