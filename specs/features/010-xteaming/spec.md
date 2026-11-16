# Spec 010 — X-Teaming multi-agent attack

> What and why. No stack, architecture or file names: those belong in `plan.md`.

- **Status:** Implemented
- **Issue:** —

## Context and goal

Myrtia has single-attacker multi-turn attacks (Crescendo, TAP/PAIR) and a multi-agent
council, but not an adaptive, plan-driven multi-agent attack. X-Teaming (Rahman et al.,
arXiv:2504.13203) coordinates four roles — a Planner that drafts diverse multi-turn
attack plans, an Attacker that executes a plan turn by turn, a Verifier that scores each
target reply, and a Prompt Optimizer that revises a stalled turn — reporting far higher
multi-turn jailbreak rates than single-strategy attacks. This feature adds X-Teaming as a
Myrtia attack plugin, reimplemented from the paper, so operators can run it against a
target and watch it live like every other attack.

## Users

- **Operator** — runs a red-teaming campaign and wants an adaptive, plan-driven
  multi-agent attack alongside the existing ones.
- **Researcher** — wants a faithful, inspectable reimplementation of X-Teaming that feeds
  the same dashboards, audit reports and traces as every other Myrtia attack.

## User stories

- **US-1** — As an operator, I want X-Teaming to appear in the attack list and run against
  any target endpoint, fully black-box, like the other attacks.
- **US-2** — As an operator, I want to see its planning, each attack turn, the target's
  reply and the verifier's score streamed live, turn by turn.
- **US-3** — As an operator, I want to set the number of plans, turns per plan, the
  success threshold and the optimization budget.
- **US-4** — As a researcher, I want the attack reimplemented from the paper (not copied
  from any repository), with its provenance and licence recorded.
- **US-5** — As a maintainer, I want no worked harmful content committed: the engine ships
  with structural, benign-by-default role prompts, and the paper-faithful operative
  prompts load from a private file, exactly as the council's Phase 2 does.

## Functional requirements

Discovery and run

- **FR-1** — THE SYSTEM SHALL register an attack `xteaming` that appears in the plugin
  list with its description, its paper reference and its "how it works" steps.
- **FR-2** — THE SYSTEM SHALL run X-Teaming fully black-box: the planner, attacker,
  verifier and optimizer are OpenAI-compatible chat endpoints, and the target is the
  run's target connector.
- **FR-3** — WHEN a run is launched with goals, THE SYSTEM SHALL attack each goal and
  return one result per goal with the best score, whether it succeeded, the plan used and
  the turns used.

The four roles

- **FR-4** — WHEN a goal starts, THE Planner SHALL produce up to N diverse attack plans
  for it (persona, context, approach and an ordered list of phase objectives), of which
  the system executes up to a configured number.
- **FR-5** — FOR each executed plan, THE Attacker SHALL produce the next turn's message
  from the plan, the current phase and the conversation so far; the message SHALL be sent
  to the target within the accumulating conversation.
- **FR-6** — WHEN the target replies, THE Verifier SHALL score on an integer 1–5 scale how
  fully the reply achieves the goal, and the phase SHALL advance when the score meets the
  phase threshold.
- **FR-7** — IF a turn's score does not improve, THEN THE Prompt Optimizer SHALL revise
  the attacker's message from textual feedback and retry, up to the optimization budget,
  before the turn moves on.
- **FR-8** — THE SYSTEM SHALL stop a plan as soon as the goal is reached (verifier score
  at or above the success threshold) and stop the goal as soon as any plan reaches it.

Live view

- **FR-9** — THE SYSTEM SHALL emit, per goal: `goal.started`; per plan: `turn.started`
  carrying the plan index; per attacker message: `proposal.created`; per target reply:
  `target.responded`; per score: `judge.scored`; and `goal.finished` with the outcome.
- **FR-10** — THE SYSTEM SHALL emit an `agent.message` event for the planner's output so
  the plans are visible in the live view.

Control

- **FR-11** — THE SYSTEM SHALL expose, as advanced configuration: number of plans, plans
  executed, max turns per plan, success score, optimization budget, and the planner,
  attacker and verifier models and endpoints.
- **FR-12** — WHILE a run is cancelled, THE SYSTEM SHALL stop between turns and plans and
  return the results gathered so far.

Content and safety

- **FR-13** — THE SYSTEM SHALL ship with structural, benign-by-default role prompts that
  make the attack run and stream but embed no worked harmful exemplars and no operational
  jailbreak guidance.
- **FR-14** — WHERE the operator points an environment variable at a private prompt file,
  THE SYSTEM SHALL load the paper-faithful operative role prompts from it; the file SHALL
  be git-ignored and SHALL NOT be committed.
- **FR-15** — THE SYSTEM SHALL record X-Teaming's provenance: reimplemented from the paper
  (arXiv:2504.13203, CC BY 4.0), no code copied from any repository; the upstream code
  repository carries no licence and is therefore not used.

## Non-functional requirements

- **NFR-1** — No new runtime dependency: X-Teaming reuses Myrtia's connectors, judge seam
  and event bus; TextGrad is reimplemented as a prompt-feedback loop, not a dependency.
- **NFR-2** — Demo-sized defaults run on a laptop; the paper's model choices are named in
  the field help.
- **NFR-3** — A missing or unreachable planner/attacker/verifier never reads as success:
  it yields a 0 score with the error as rationale, and the run continues.
- **NFR-4** — Secrets are never emitted: API keys and auth headers stay out of events, as
  for every other plugin.

## Edge cases

- The planner returns no usable plan: the goal is scored 0 and reported as not succeeded.
- A plan has one phase: it behaves like a single-objective multi-turn attack.
- The optimizer never improves a turn: after the budget the plan moves on or ends.
- The target refuses every turn of every plan: the goal is reported with the best (low)
  score seen.
- The private prompt file is absent: the attack runs with the benign defaults.
- A malformed private prompt file: the attack falls back to the defaults and logs why.

## Out of scope

- White-box / gradient optimization (the paper's TextGrad uses a textual gradient only,
  which this reimplements; no model weights are touched).
- XGuard-Train (the paper's defensive dataset) and any training.
- Automatic generation of worked harmful plan exemplars.
- Copying or vendoring the authors' code repository.

## Acceptance scenarios

The scenarios are in `backend/tests/features/xteaming.feature` (offline tier, with stub
planner/attacker/verifier connectors — no network, no live model):

```gherkin
Scenario: X-Teaming runs a plan to success               # FR-4, FR-5, FR-6, FR-8
  Given an X-Teaming run with 1 plan of 2 phases
  And the verifier scores the second turn a full 5
  When the attack runs against a stub target
  Then the goal is reported as succeeded at turn 2
  And the live view saw a plan, two attacker messages, two target replies and two scores

Scenario: A stalled turn is optimized before moving on    # FR-7
  Given an X-Teaming run whose first attacker message scores 1
  And the optimizer budget is 2
  When the attack runs against a stub target
  Then the optimizer revised the message before the next phase
```

Manual check:

- With a private prompt file set and a live local model, launch an X-Teaming run and watch
  the plan, turns, replies and scores stream in the UI (covers FR-2, FR-9, FR-14).

## Definition of done

1. Every acceptance scenario passes, and each was seen failing before the code existed.
2. `ruff check backend` and `pytest -m "not e2e"` pass.
3. The plugin appears in `/plugins` and a run completes against a stub target.

## Open questions

None. Decided by the maintainer: reimplement from the paper, never copy the unlicensed
repository; operative prompts load from a private file, as the council's Phase 2 does.
