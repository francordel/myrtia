Feature: Agent Targets
  As an AI safety researcher or agent builder
  I want to target multi-step tool-using agents in Myrtia
  So that tool calls, handoffs, and forbidden actions are traced and measured

  Scenario: Sandbox agent executes a tool call and a handoff traced as structured events
    Given a sandbox agent target backed by a simulated model
    When an attack sends a prompt that triggers a tool call and a specialist handoff
    Then the connector emits "agent.tool_called", "agent.tool_responded", and "agent.handoff"
    And no forbidden action is flagged when only safe tools are used

  Scenario: Forbidden tool call by the agent counts as attack success
    Given a sandbox agent target with forbidden action rules
    When an attack tricks the agent into calling a restricted exfiltration tool
    Then "agent.forbidden_action" is emitted
    And the target connector records the forbidden action as an attack success

  Scenario: SSRF guard blocks metadata endpoints on agent target
    Given an agent target spec pointing to a cloud metadata address
    When the target connector is built
    Then the SSRF guard rejects the target URL

  @e2e
  Scenario: Live local model drives the sandbox agent target end-to-end
    Given a live local model endpoint configured for the sandbox agent target
    When a prompt is sent through the agent target connector
    Then the agent completes and returns a valid response

