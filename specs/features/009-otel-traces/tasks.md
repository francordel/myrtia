# Tasks 009 — Run traces with OpenTelemetry

> Small tasks in dependency order. Implement one at a time, test first: write the failing
> scenario or unit test, make it pass with the minimum code, refactor, run the checks,
> tick the box, stop.

- [x] **T1 — Write the acceptance scenarios** (FR-1 … FR-18)
  Add `backend/tests/features/tracing.feature` and `backend/tests/test_tracing.py`,
  recording spans in memory.
  Done when: the scenarios are collected and fail because `myrtia.tracing` does not exist.

- [x] **T2 — Optional dependency and configuration** (FR-1 … FR-4, NFR-1)
  `otel` extra; `tracing.configure`, `status`, `use_exporter`, `reset`, `shutdown`.
  Done when: the off-by-default, missing-packages and blocked-address scenarios pass.

- [x] **T3 — Run, goal and turn spans from events** (FR-5, FR-6, FR-9)
  `observe_event` with the per-run stack; hook in the event bus.
  Done when: the nesting and failed-run scenarios pass.

- [x] **T4 — Model-call spans** (FR-7, FR-15)
  `start_model_call` and its use in the connector wrapper.
  Done when: the model-call, single-shot and failure-isolation scenarios pass.

- [x] **T5 — Events and verdicts** (FR-8, FR-10)
  Other events become span events; the score lands on the turn.
  Done when: both scenarios pass.

- [x] **T6 — Content rules** (FR-11 … FR-14)
  Content on by default, off switch, scrubbing, truncation.
  Done when: the four content scenarios pass.

- [x] **T7 — Report and shutdown** (FR-4)
  `/observability` reports tracing; spans are flushed when the app stops.
  Done when: the console scenario passes.

- [x] **T8 — Trace store and dashboard** (FR-16 … FR-18)
  Tempo in the stack, its data source, "Myrtia traces", links between dashboards.
  Done when: the stack and dashboard scenarios pass.

- [x] **T9 — Documentation**
  `docs/observability.md`, `README.md`, `AGENTS.md`, roadmap row.
  Done when: a reader can switch tracing on and find a run's trace from the docs alone.

- [x] **T11 — Traces control in the console** (FR-19 … FR-22)
  Scenarios first (UI tier), then `traces_url` and the start command in `/observability`,
  the header control and the dialog text.
  Done when: the scenarios pass in the browser tier and the control was used by hand.

- [x] **T10 — Validate the spec**
  Walk `spec.md` requirement by requirement, run the checks, trace a real run and open it
  in the dashboard.
  Done when: every requirement is covered and the verdict is written in the pull request.
