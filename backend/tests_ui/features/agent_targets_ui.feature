Feature: Agent Targets UI integration
  As a red-teamer
  I want to select the Sandbox Agent target in the UI and see its tool/handoff events clearly
  So that I can run attacks against multi-step agents from the browser

  Scenario: Sandbox Agent target is selectable in the provider dropdown
    Given the Myrtia console is open
    When I select the "agent_sdk" target provider
    Then the target kind is "agent_sdk"

  Scenario: Sandbox Agent target is selectable in the Agentic graph builder
    Given the Myrtia console is open
    When I set the graph target node kind to "agent_sdk"
    Then the graph payload target kind is "agent_sdk"

  Scenario: Agent target events render with human-readable labels and forbidden warning styling
    Given the Myrtia console is open
    When agent target events are rendered in the live trace
    Then the live trace shows role "Agent tool"
    And the live trace shows role "Agent handoff"
    And the live trace shows a blocked warning for "Forbidden agent action"

