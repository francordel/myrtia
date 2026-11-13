# Spec 009 — Run traces with OpenTelemetry

> What and why. No stack, architecture or file names: those belong in `plan.md`.

- **Status:** Implemented
- **Issue:** —
- **Depends on:** 008 (observability metrics)

## Context and goal

The metrics of spec 008 say how much and how fast, in aggregate. They do not say what
happened inside one run: which agent spoke when, what it sent, what came back, how long
each step took and which verdict followed. This feature makes Myrtia emit each run as a
trace in the OpenTelemetry format, so a run can be followed step by step and kept as an
audit record, in any tool that reads the standard.

## Users

- **Operator** — wants to open one run and see its steps as a timeline, with durations.
- **Auditor** — needs the full record of a run: who did what, in which order, with which
  content and which verdict.
- **Maintainer** — wants Myrtia's telemetry to work with standard tooling, not one tool.

## User stories

- **US-1** — As an operator, I want a run shown as a tree of steps (run, goal, turn,
  model call) with durations so that I can see where the time goes and which agent acted.
- **US-2** — As an auditor, I want each step to carry what was sent and what came back so
  that a run can be reviewed end to end without the console.
- **US-3** — As an auditor, I want trace data kept on the machine and out of the
  repository unless someone exports it on purpose.
- **US-4** — As a maintainer, I want the traces in the OpenTelemetry format so that any
  compatible store or viewer can read them.
- **US-5** — As an operator, I want a list of recent runs on the dashboard that opens the
  trace of the one I pick.

## Functional requirements

Switching it on

- **FR-1** — THE SYSTEM SHALL emit no traces unless the operator switches tracing on.
- **FR-2** — WHERE tracing is on, THE SYSTEM SHALL export traces in the OpenTelemetry
  protocol to the address the operator sets, by default a collector on the same machine.
- **FR-3** — IF tracing is switched on but its packages are not installed or its address
  is not allowed, THEN THE SYSTEM SHALL keep running without traces and say why.
- **FR-4** — THE SYSTEM SHALL report whether tracing is on, and why not when it is not.

Shape of a trace

- **FR-5** — WHEN a run starts, THE SYSTEM SHALL open one trace for it whose root step
  carries the run's identifier, attack, target model, number of goals and purpose.
- **FR-6** — WHEN a goal starts, THE SYSTEM SHALL open a step for it under the run; WHEN a
  turn starts, a step for it under its goal.
- **FR-7** — WHEN a model is called during a run, THE SYSTEM SHALL record a step under the
  innermost open step of that run, with the caller's role, the model, the duration, the
  outcome and the tokens the reply reported.
- **FR-8** — WHEN any other event of the run is published (proposal, critique, vote,
  synthesis, target response, verdict, shield action, approval), THE SYSTEM SHALL attach
  it, with its time, to the innermost open step of that run.
- **FR-9** — WHEN a run finishes, THE SYSTEM SHALL close every step still open and record
  the run's final status; IF the run failed, THEN the root step SHALL be marked as an
  error with the reason.
- **FR-10** — WHEN a judge scores a response, THE SYSTEM SHALL record the score on the
  step of the turn (or goal) it belongs to.

Content

- **FR-11** — THE SYSTEM SHALL include content in the trace by default: the messages sent
  to each model, each reply, and the text carried by each event.
- **FR-12** — WHERE the operator switches content off, THE SYSTEM SHALL keep the structure,
  timings, roles, models, tokens and scores, and leave the text out.
- **FR-13** — THE SYSTEM SHALL NOT put API keys, auth header names or header values in a
  trace, and SHALL scrub key-shaped strings from content.
- **FR-14** — IF a piece of content is longer than the limit (20 000 characters by
  default), THEN THE SYSTEM SHALL cut it there and mark it as truncated.

Safety

- **FR-15** — IF recording a trace fails, THEN THE SYSTEM SHALL let the model call and
  the run continue unaffected.
- **FR-16** — THE SYSTEM SHALL keep trace data out of the repository and out of the
  application image by default.

Viewing

- **FR-17** — WHERE the operator starts the optional observability stack, THE SYSTEM SHALL
  also bring up a trace store, reachable only from the local machine, and provision it in
  Grafana.
- **FR-18** — THE stack SHALL provide a "Myrtia traces" dashboard that lists recent runs
  and shows the step timeline of the one the operator picks, and SHALL link it with the
  overview dashboard in both directions.

## Non-functional requirements

- **NFR-1** — Optional dependency: the default install is unchanged; without the tracing
  packages nothing is imported and nothing fails.
- **NFR-2** — With tracing off, the cost per model call and per event is one check.
- **NFR-3** — Spans are exported in the background; a slow or absent collector never
  delays a model call.
- **NFR-4** — Span names and attribute names follow the OpenTelemetry conventions for
  generative AI where one exists, and a `myrtia.` prefix otherwise.
- **NFR-5** — The trace store sends no usage reports.

## Edge cases

- A run that never emits goals or turns (single-shot attacks): model calls hang directly
  under the run.
- A plugin that does not announce the end of a goal: the next goal, or the end of the
  run, closes it.
- A model call outside any run (preflight): not traced.
- A run that finishes without a recorded start (after a restart): ignored.
- Model calls an attack makes from threads it starts itself: they may not be attached to
  the run and are then not traced.
- Traces contain whatever the models produced, including harmful text. They are run
  results and are handled as such (FR-16).

## Out of scope

- Shipping logs.
- A "view trace" link from a run inside the console.
- Sampling: every run is traced when tracing is on.
- Rebuilding traces for runs executed before tracing was switched on.
- Tracing inside the vendored council's own model client.

## Acceptance scenarios

The scenarios are in `backend/tests/features/tracing.feature` (offline tier, spans
recorded in memory):

```gherkin
Scenario: A run becomes one trace of nested steps          # FR-5, FR-6, FR-7, FR-9
  Given tracing is on
  When a run with one goal and one turn calls its target once and finishes
  Then there is one trace with the steps "run", "goal", "turn" and "chat"
  And each step is nested under the one before

Scenario: Tracing is off by default                         # FR-1
  Given tracing has not been switched on
  When a run with one goal and one turn calls its target once and finishes
  Then no step is recorded
```

Manual checks:

- Start the stack with tracing on, launch a run, open "Myrtia traces": the run is listed
  and its timeline shows goals, turns and model calls with their content (FR-17, FR-18).

## Definition of done

1. Every acceptance scenario passes, and each was seen failing before the code existed.
2. `ruff check backend` and `pytest -m "not e2e"` pass; the UI tier still passes.
3. A real run's trace was seen in the dashboard.

## Open questions

None. Decided by the maintainer: traces carry full content so runs are auditable; trace
data stays out of the repository by default.
