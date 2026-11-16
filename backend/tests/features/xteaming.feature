Feature: X-Teaming multi-agent attack
  X-Teaming (reimplemented from arXiv:2504.13203) coordinates a planner, an attacker, a
  verifier and a prompt optimizer to run adaptive, plan-driven multi-turn jailbreaks,
  streamed and scored like every other Myrtia attack (spec 010).

  # --- discovery ---------------------------------------------------------------
  Scenario: X-Teaming is registered and described                     # FR-1
    When I look up the "xteaming" plugin
    Then it is registered
    And it has a description, a paper reference and how-it-works steps

  Scenario: The advanced configuration lists every knob               # FR-11
    When I look up the "xteaming" plugin
    Then its configuration offers n_plans, n_execute, max_turns, success_score and opt_budget

  # --- running a plan ----------------------------------------------------------
  Scenario: X-Teaming runs a plan to success                          # FR-3,4,5,6,8
    Given an X-Teaming attack whose planner returns 1 plan of 2 phases
    And the verifier scores the turns 2 then 5
    When the attack runs against a stub target
    Then the goal is reported as succeeded
    And the best score is 5
    And 2 turns were used

  Scenario: The live view sees the plan, the turns, the replies and the scores  # FR-9,10
    Given an X-Teaming attack whose planner returns 1 plan of 2 phases
    And the verifier scores the turns 2 then 5
    When the attack runs against a stub target
    Then the planner's plan was emitted as an agent message
    And there were 2 attacker proposals, 2 target replies and 2 scores

  Scenario: A stalled turn is optimized before moving on              # FR-7
    Given an X-Teaming attack whose planner returns 1 plan of 1 phase
    And the first attacker message scores 1, then the optimized message scores 5
    And the optimizer budget is 2
    When the attack runs against a stub target
    Then the attacker message was optimized before the goal was reached
    And the goal is reported as succeeded

  Scenario: An unreachable verifier does not read as success          # NFR-3
    Given an X-Teaming attack whose planner returns 1 plan of 1 phase
    And the verifier endpoint is unreachable
    When the attack runs against a stub target
    Then the goal is reported as not succeeded
    And the best score is 0

  Scenario: A malformed plan falls back to a single-phase plan        # edge case
    Given an X-Teaming attack whose planner returns nothing usable
    And the verifier scores the turns 5
    When the attack runs against a stub target
    Then the attack still ran one plan against the target
    And the goal is reported as succeeded

  Scenario: A cancelled run stops and returns what it has             # FR-12
    Given an X-Teaming attack whose planner returns 1 plan of 3 phases
    And the run is cancelled after the first turn
    When the attack runs against a stub target
    Then the attack stopped early and returned a result for the goal

  # --- content and safety ------------------------------------------------------
  Scenario: The committed defaults carry no worked harmful content    # FR-13
    When the default role prompts are loaded
    Then there are prompts for the planner, attacker, verifier and optimizer
    And none of them contains a worked harmful exemplar

  Scenario: A private prompt file overrides the defaults              # FR-14
    Given a private prompt file that sets the planner prompt to "PRIVATE PLANNER"
    When the role prompts are loaded
    Then the planner prompt is "PRIVATE PLANNER"

  Scenario: A missing private file falls back to the defaults         # FR-14
    Given the private prompt file is set to a path that does not exist
    When the role prompts are loaded
    Then the planner prompt is the committed default

  # --- provenance --------------------------------------------------------------
  Scenario: The provenance is recorded                                # FR-15
    Then the third-party notices record X-Teaming as reimplemented from the paper
    And they state that the upstream repository carries no licence and is not used
