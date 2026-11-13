# Tasks 008 — Observability metrics and dashboard

> Small tasks in dependency order. Implement one at a time, test first: write the failing
> scenario or unit test, make it pass with the minimum code, refactor, run the checks,
> tick the box, stop.

- [x] **T1 — Write the acceptance scenarios** (FR-1 … FR-19)
  Add `backend/tests/features/observability.feature` and its steps in
  `backend/tests/test_observability.py`.
  Done when: the scenarios are collected and fail because `myrtia.telemetry` does not
  exist.

- [x] **T2 — Registry and text rendering** (FR-1, FR-3, FR-15, NFR-2, NFR-4)
  `myrtia/telemetry.py`: metric catalogue, counters, gauges, histograms, label escaping,
  `render()`, `reset()`.
  Done when: the rendering scenario passes.

- [x] **T3 — Model-call recording** (FR-4, FR-5, FR-6, FR-16)
  `record_model_call` and the `observed` wrapper on the three connectors.
  Done when: the successful, failed, no-usage and failure-isolation scenarios pass.

- [x] **T4 — Roles** (FR-7)
  `role` in the factory spec; orchestrator, judge, shields, crescendo, TAP, graph and
  preflight pass theirs.
  Done when: the role scenario passes and the existing offline suite is still green.

- [x] **T5 — Run, judge, shield and event metrics** (FR-8 … FR-12)
  `observe_event` and the hook in the event bus.
  Done when: the run, judge, shield and event scenarios pass.

- [x] **T6 — Per-run series with a cap** (FR-13, FR-14)
  `bind_run`, the context copy in the orchestrator, eviction of the oldest finished run.
  Done when: both per-run scenarios pass.

- [x] **T7 — Metrics address** (FR-1, FR-2)
  `api/routers/metrics.py`, mounted in `api/app.py`, with the token gate.
  Done when: the address and token scenarios pass.

- [x] **T8 — Stack and dashboard** (FR-17, FR-18, FR-19, NFR-5)
  `compose.observability.yaml`, `observability/` provisioning and the dashboard.
  Done when: the dashboard and Compose scenarios pass.

- [x] **T9 — Documentation** (FR-17)
  `docs/observability.md`, a short section in `README.md`, the command in `AGENTS.md`,
  the roadmap row.
  Done when: a reader can start the stack from the docs alone.

- [x] **T11 — Console to dashboard and back** (FR-20 … FR-24)
  Scenarios first (offline and UI tier), then `GET /observability`, the header control
  with its dialog, and the "Open Myrtia" link in the dashboard.
  Done when: the new scenarios pass in both tiers and both links were followed by hand.

- [x] **T10 — Validate the spec**
  Walk `spec.md` requirement by requirement, run the checks, start the stack and watch a
  run on the dashboard.
  Done when: every requirement is covered and the verdict is written in the pull request.
