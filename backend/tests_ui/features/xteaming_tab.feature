Feature: X-Teaming run-mode tab
  X-Teaming has its own run-mode tab beside the agentic graph builder, so the multi-agent
  attack is one click to configure and launch (spec 012).

  Scenario: The X-Teaming tab selects the plugin
    Given the Myrtia console is open
    When I open the X-Teaming run mode
    Then the attack is set to "xteaming"
    And its description mentions X-Teaming
    And the attack-plugin selector is hidden
    And the graph canvas is hidden
