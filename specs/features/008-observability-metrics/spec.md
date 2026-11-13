# Spec 008 — Observability metrics and dashboard

> What and why. No stack, architecture or file names: those belong in `plan.md`.

- **Status:** Implemented
- **Issue:** —

## Context and goal

Myrtia shows one run at a time in its live view and aggregates results in its statistics
page, but nothing answers operational questions while runs are in flight: how many
tokens each role is consuming, how slow each model is, how often calls fail, how many
runs are active. This feature makes Myrtia export those numbers as metrics and ships an
optional, ready-made Grafana dashboard that reads them in real time.

## Users

- **Operator** — runs red-teaming campaigns and wants to see cost (tokens), speed
  (latency) and activity per role, per model and per run while they happen.
- **Maintainer** — wants to spot a slow or failing model endpoint without reading logs.

## User stories

- **US-1** — As an operator, I want token consumption per role and per model in real
  time so that I know what a campaign costs while it runs.
- **US-2** — As an operator, I want the latency of every model so that I can tell which
  one is holding a run back.
- **US-3** — As an operator, I want to pick one recent run and see its calls, tokens and
  model time per role so that I can compare runs.
- **US-4** — As a maintainer, I want one command that starts a dashboard already wired
  to Myrtia so that I do not configure anything by hand.
- **US-6** — As an operator, I want one click from the console to the dashboard and one
  click back so that I do not have to remember addresses.
- **US-5** — As a maintainer, I want the metrics in a standard format so that any
  compatible collector can read them, not only the bundled one.

## Functional requirements

Metrics export

- **FR-1** — THE SYSTEM SHALL serve its current metrics at one address in the Prometheus
  text exposition format, with a help line and a type line for every metric.
- **FR-2** — IF an access token is configured, THEN THE SYSTEM SHALL refuse a metrics
  request that does not carry it, and SHALL accept it as a bearer credential.
- **FR-3** — THE SYSTEM SHALL start every counter at zero when the process starts; it
  SHALL NOT rebuild metrics from stored runs.

Model calls

- **FR-4** — WHEN a call to a model finishes, THE SYSTEM SHALL count it by role, model
  and outcome (`ok` or `error`).
- **FR-5** — WHEN a call to a model finishes, THE SYSTEM SHALL record its duration in a
  latency distribution by role and model.
- **FR-6** — WHEN a model reply reports token usage, THE SYSTEM SHALL add the prompt
  tokens and the completion tokens to counters by role and model.
- **FR-7** — THE SYSTEM SHALL label each call with the role of its caller: `target`,
  `judge`, `defense`, `preflight`, the agent's role in a graph attack (`attacker`,
  `chairman`), and `aux` for any other auxiliary model.

Runs and events

- **FR-8** — WHEN a run starts, THE SYSTEM SHALL count it by attack and raise the number
  of active runs for that attack.
- **FR-9** — WHEN a run finishes, THE SYSTEM SHALL count it by attack and final status,
  lower the number of active runs, and record the run's duration by attack.
- **FR-10** — WHEN a judge scores a response, THE SYSTEM SHALL count the verdict by
  attack and score.
- **FR-11** — WHEN a shield transforms or blocks a prompt or a response, THE SYSTEM SHALL
  count it by shield and action (`applied` or `blocked`).
- **FR-12** — WHEN any event is published on a run's stream, THE SYSTEM SHALL count it
  by event type.

Per-run view

- **FR-13** — WHILE a run is among the most recent runs (20 by default), THE SYSTEM SHALL
  expose its model calls, tokens and model time by run, attack and role.
- **FR-14** — WHEN a new run would exceed that limit, THE SYSTEM SHALL drop the series of
  the oldest finished run, so the number of per-run series stays bounded.

Safety

- **FR-15** — THE SYSTEM SHALL NOT put prompts, responses, goals, API keys, header names
  or endpoint addresses in any metric name, label or value.
- **FR-16** — IF recording a metric fails, THEN THE SYSTEM SHALL let the model call and
  the run continue unaffected.

Dashboard

- **FR-17** — WHERE the operator starts the optional observability stack, THE SYSTEM
  SHALL bring up a metrics collector and Grafana with the data source and a "Myrtia
  overview" dashboard already provisioned, reachable only from the local machine and
  viewable without logging in.
- **FR-18** — THE dashboard SHALL show: active runs, finished runs by status, tokens per
  minute by role, latency (median and 95th percentile) by role, calls by model and
  outcome, tokens by model, judge score distribution, shield actions, events per minute
  by type, and, for a run chosen in a filter, its tokens, calls and model time by role.
- **FR-19** — THE dashboard SHALL query only metrics the system exports.

Getting there and back

- **FR-20** — THE console SHALL show a "Dashboard" control in its header.
- **FR-21** — WHEN the operator activates that control and the dashboard is reachable,
  THE SYSTEM SHALL open the dashboard in a new tab, leaving the console as it was.
- **FR-22** — IF the dashboard is not reachable when the control is activated, THEN THE
  SYSTEM SHALL say so, show the command that starts it, and offer to open it anyway.
- **FR-23** — WHERE the operator has switched the dashboard address off, THE SYSTEM SHALL
  hide the control.
- **FR-24** — THE dashboard SHALL offer an "Open Myrtia" link back to the console, at an
  address the operator can set.

## Non-functional requirements

- **NFR-1** — No new runtime dependency: the default install and `uv run myrtia` are
  unchanged, and nothing extra starts unless the operator asks for the stack.
- **NFR-2** — Recording a model call costs constant time and no network or disk access.
- **NFR-3** — Label values are bounded: roles, outcomes, statuses and scores come from
  fixed sets; models and attacks come from the operator's configuration; run labels are
  capped (FR-14). User-typed agent names are never labels.
- **NFR-4** — Safe from any thread: model calls happen in worker threads while the
  metrics address is read from the server loop.
- **NFR-5** — The stack sends no usage analytics and checks for no updates.

## Edge cases

- A model reply without usage data: the call and its latency are recorded, tokens are
  not.
- A failed call (transport error, HTTP error, empty reply): counted with outcome
  `error`, latency recorded.
- A run finishing without a recorded start (for example after a restart): counted as
  finished under attack `unknown`; the active-runs number never goes below zero.
- A judge score outside 0–5: counted under score `invalid`.
- A model call made outside any run (preflight): counted in the global metrics, in no
  per-run series.
- A label value containing a quote, a backslash or a line break is escaped.
- More than the limit of runs still running at once: the oldest run is dropped even if
  it has not finished.

- The console runs in Docker and cannot reach the dashboard's address itself although the
  operator's browser can: the control reports it as not reachable and "Open anyway"
  still works.

## Out of scope

- Distributed traces and log shipping (stay in the backlog as their own feature).
- Alerting rules, cost in currency, long-term retention policy.
- Embedding the dashboard inside Myrtia's own UI (the console links to it instead).
- Metrics for the vendored council's internal model calls that do not go through
  Myrtia's connectors.

## Acceptance scenarios

The scenarios are in `backend/tests/features/observability.feature` (offline tier):

```gherkin
Scenario: A successful model call is counted with its tokens      # FR-4, FR-5, FR-6, FR-7
  Given a judge connector for model "sim-judge"
  And the model replies with 12 prompt tokens and 30 completion tokens
  When the connector is called once
  Then the metrics count 1 "ok" call for role "judge" and model "sim-judge"
  And the metrics count 12 "prompt" and 30 "completion" tokens for role "judge"
  And the latency distribution for role "judge" holds 1 observation

Scenario: Only the most recent runs keep per-run series            # FR-13, FR-14
  Given the per-run limit is 2
  When model calls are recorded for runs "r1", "r2" and "r3" in that order
  Then the metrics hold per-run series for "r2" and "r3"
  And the metrics hold no per-run series for "r1"
```

Manual checks:

- Start the stack, launch a run, open Grafana: the "Myrtia overview" dashboard opens
  without a login and its panels fill while the run progresses (covers FR-17, FR-18).

## Definition of done

1. Every acceptance scenario passes, and each was seen failing before the code existed.
2. `ruff check backend` and `pytest -m "not e2e"` pass.
3. The dashboard was seen showing a real run.

## Open questions

None. Decisions taken without asking, recorded in `plan.md`: per-run labels are capped
rather than unbounded; traces are left for a later feature; the metrics address follows
the same access token as the rest of the API.
