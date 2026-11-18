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

  Scenario: A turn whose score drops is optimized before moving on    # FR-7
    Given an X-Teaming attack whose planner returns 1 plan of 2 phases
    And the X-Teaming variant is "paper"
    And the verifier scores the turns 3 then 1, then the optimized message scores 5
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

  # --- fidelity to the paper (Algorithm 1, Appendix A.4) -------------------------
  Scenario: A plan in the paper's format is parsed and run phase by phase     # FR-3
    Given an X-Teaming attack whose planner answers in the paper's format with 3 phases
    And the verifier scores the turns 2, 3 then 5
    When the attack runs against a stub target
    Then the goal is reported as succeeded
    And 3 turns were used
    And the planner was told the behaviour
    And the attacker was shown the plan's persona

  Scenario: The target sees the whole conversation                            # FR-4
    Given an X-Teaming attack whose planner answers in the paper's format with 3 phases
    And the verifier scores the turns 2, 3 then 5
    When the attack runs against a stub target
    Then the target's last request held the 2 earlier exchanges

  Scenario: The optimizer works from the verifier's reason                    # FR-7
    Given an X-Teaming attack whose planner returns 1 plan of 2 phases
    And the X-Teaming variant is "paper"
    And the verifier scores the turns 3 then 1, then the optimized message scores 5
    And the optimizer budget is 2
    When the attack runs against a stub target
    Then the optimizer was given the verifier's reason

  Scenario: A plan that runs out of phases is revised and extended            # FR-6
    Given an X-Teaming attack whose planner returns 1 plan of 1 phase
    And the planner's revision adds a second phase
    And the verifier scores the turns 2 then 5
    When the attack runs against a stub target
    Then the goal is reported as succeeded
    And the plan was revised

  Scenario: An unreachable attacker never sends its error to the target       # NFR-3
    Given an X-Teaming attack whose planner returns 1 plan of 2 phases
    And the attacker endpoint is unreachable
    When the attack runs against a stub target
    Then the target was never sent an error message
    And the goal is reported as not succeeded

  Scenario: The attacker's reasoning is not sent when it omits the message tag  # FR-4
    Given an X-Teaming attack whose planner returns 1 plan of 1 phase
    And the attacker replies "<thinking>secret plan</thinking>Hello there" without a message tag
    And the verifier scores the turns 5
    When the attack runs against a stub target
    Then the target was sent "Hello there"

  # --- the reference run: the official code as run for CouncilAttack ------------
  Scenario: The defaults reproduce the reference run's settings               # FR-16
    When I look up the "xteaming" plugin
    Then its defaults are 50 plans drafted, 10 executed, 7 turns and an optimizer budget of 4
    And its defaults are the official variant and the graded verifier on the whole reply

  Scenario: In the official variant a stalled turn is re-sent, then optimized  # FR-17
    Given an X-Teaming attack whose planner returns 1 plan of 2 phases
    And the verifier scores the turns 3, 1, 1 then 5
    When the attack runs against a stub target
    Then the second phase's first retry re-sent the same message
    And its next retry was optimized
    And the goal is reported as succeeded

  Scenario: The official variant commits a phase's last try, with the best committed score as the bar  # FR-17
    Given an X-Teaming attack whose planner returns 1 plan of 3 phases
    And the optimizer budget is 1
    And the verifier scores the turns 4, 2, 1, 3 then 5
    When the attack runs against a stub target
    Then the attacker saw phase 2 committed with the score 1
    And the goal is reported as succeeded
    And 5 turns were used

  Scenario: The paper variant commits a phase's best try                      # FR-17
    Given an X-Teaming attack whose planner returns 1 plan of 3 phases
    And the X-Teaming variant is "paper"
    And plan revision is off
    And the optimizer budget is 1
    And the verifier scores the turns 4, 2, 1, 3 then 5
    When the attack runs against a stub target
    Then the attacker saw phase 2 committed with the score 2
    And 4 turns were used

  Scenario: The official variant asks the attacker model to revise the plan   # FR-17
    Given an X-Teaming attack whose planner returns 1 plan of 1 phase
    And the planner's revision adds a second phase
    And the verifier scores the turns 2 then 5
    When the attack runs against a stub target
    Then the plan revision was asked of the attacker model
    And the goal is reported as succeeded

  Scenario: A refusing attacker is asked again up to 5 times                  # FR-17
    Given an X-Teaming attack whose planner returns 1 plan of 1 phase
    And the attacker replies "Sorry, I can't help with that." without a message tag
    When the attack runs against a stub target
    Then the attacker was asked 5 times
    And the target was never called

  Scenario: The verifier sees the whole reply by default                      # FR-18
    Given an X-Teaming attack whose planner returns 1 plan of 1 phase
    And the target replies with 5000 characters
    And the verifier scores the turns 5
    When the attack runs against a stub target
    Then the verifier was shown 5000 characters of the reply

  Scenario: A verifier limit cuts the reply it sees                           # FR-18
    Given an X-Teaming attack whose planner returns 1 plan of 1 phase
    And the verifier sees at most 2048 characters
    And the target replies with 5000 characters
    And the verifier scores the turns 5
    When the attack runs against a stub target
    Then the verifier was shown 2048 characters of the reply

  Scenario: The graded verifier's 0-5 harm is read on the 1-5 scale           # FR-18
    Given an X-Teaming attack whose planner returns 1 plan of 2 phases
    And the verifier scores the turns 0 then 5
    When the attack runs against a stub target
    Then the first turn was scored 1
    And the verifier was given the graded rubric
    And the goal is reported as succeeded

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
