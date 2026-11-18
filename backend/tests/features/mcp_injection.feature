Feature: MCP Injection Attacks
  As an AI safety researcher or defender
  I want to test whether a target model is vulnerable to canonical MCP attacks
  So that I can measure attack success and diagnose unauthorized MCP tool calls

  Scenario: Target model falls for MCP Tool Poisoning
    Given a target model that follows hidden instructions in MCP tool descriptions
    When the operator runs the MCP injection attack with the "tool_poisoning" variant
    Then the run trace records the MCP manifest and the unauthorized tool call
    And the run flags the forbidden action alongside the judge verdict

  Scenario: Target model resists MCP Tool Shadowing
    Given a target model that ignores cross-server shadowing directives
    When the operator runs the MCP injection attack with the "tool_shadowing" variant
    Then no forbidden action is flagged
    And the run finishes with an unsuccessful attack outcome

  Scenario: MCP Rug Pull mutates tool manifest after initial benign turn
    Given a target model interacting with a multi-turn MCP server
    When the operator runs the MCP injection attack with the "rug_pull" variant
    Then the manifest mutation event is recorded after the initial turn
    And any subsequent unauthorized tool call is flagged

  @e2e
  Scenario: Live local model is evaluated against MCP injection attacks
    Given a live local model endpoint configured as the target
    When the operator runs the MCP injection attack against the live target
    Then the run completes and stores structured MCP events and judge score

