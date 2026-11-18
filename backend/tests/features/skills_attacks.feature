Feature: Agent Skills Attacks
  As an AI safety researcher or defender
  I want to test whether a target model is vulnerable to skill-embedded prompt injections
  So that I can measure attack success and diagnose unauthorized tool calls

  Scenario: Target model complies with a subtle SKILL-INJECT payload
    Given a target model that follows instructions in loaded skill files
    When the operator runs the Agent Skills attack with the "contextual_exfil" variant
    Then the run trace records the loaded skill and the simulated unauthorized tool call
    And the run flags the forbidden action alongside the judge verdict

  Scenario: Target model refuses a poisoned skill and completes only the benign task
    Given a target model that ignores injected directives in skill metadata
    When the operator runs the Agent Skills attack with the "yaml_metadata_poison" variant
    Then no forbidden tool call is flagged
    And the run finishes with an unsuccessful attack outcome

  Scenario: Companion resource indirect injection triggers on resource read
    Given a skill that instructs the model to inspect a companion resource
    When the target model reads the companion resource and receives the injected payload
    Then the simulated resource read and any subsequent tool call are recorded in the run events

  @e2e
  Scenario: Live local model is evaluated against the Agent Skills attack suite
    Given a live local model endpoint configured as the target
    When the operator runs the Agent Skills attack against the live target
    Then the run completes and stores the structured skill-loop events and judge score

