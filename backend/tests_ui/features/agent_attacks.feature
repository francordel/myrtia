Feature: Agent Skills and MCP Injection UI rendering
  As a red-teamer
  I want Agent Skills and MCP injection attacks to appear in the UI and render their events clearly
  So that I can launch them and read tool calls, manifest mutations, and forbidden actions

  Scenario: Skills and MCP plugins are selectable with their configuration fields
    Given the Myrtia console is open
    When I select the "skills-attacks" attack
    Then the attack configuration shows "Skill attack variants"
    When I select the "mcp-injection" attack
    Then the attack configuration shows "MCP attack variants"

  Scenario: Skill events render with human-readable labels and forbidden warning styling
    Given the Myrtia console is open
    When skill attack events are rendered in the live trace
    Then the live trace shows role "Skill"
    And the live trace shows role "Skill tool"
    And the live trace shows a blocked warning for "Forbidden skill action"

  Scenario: MCP events render with human-readable labels and mutation/forbidden styling
    Given the Myrtia console is open
    When MCP injection events are rendered in the live trace
    Then the live trace shows role "MCP manifest"
    And the live trace shows a blocked warning for "MCP mutated"
    And the live trace shows role "MCP tool"
    And the live trace shows a blocked warning for "Forbidden MCP action"

