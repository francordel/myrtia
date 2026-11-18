# Plan 008 — Observability metrics and dashboard

> How the spec will be built. Read `specs/constitution/` and this feature's `spec.md`
> first. Every part names the requirements it covers.

## Approach

A small in-process metrics registry (`myrtia.telemetry`, standard library only) holds
counters, gauges and histograms behind one lock and renders them in the Prometheus text
format. It is fed from the two places every run already passes through: the connectors
(one wrapper around `generate()` measures each model call) and the event bus (each
published event updates the run, judge and shield metrics). A new router serves the
registry at `GET /metrics`. An opt-in Compose file starts Prometheus and Grafana with a
provisioned data source and dashboard; a test keeps the dashboard's queries in step with
the metric names the registry declares.

## Affected areas

| Area | Change | Covers |
|---|---|---|
| `backend/myrtia/telemetry.py` (new) | Registry, metric catalogue, text rendering, `record_model_call`, `observe_event`, `bind_run`, per-run cap | FR-1, FR-3 … FR-16 |
| `backend/myrtia/connectors/base.py` | `observed` wrapper on the three `generate()` methods; `role` attribute | FR-4 … FR-7, FR-16 |
| `backend/myrtia/connectors/factory.py` | Optional `role` in the spec, default `aux` | FR-7 |
| `backend/myrtia/orchestrator/runner.py` | Marks the run's connector `target`; binds the run to the worker's context | FR-7, FR-13 |
| `backend/myrtia/judges/graded.py`, `defenses.py`, `plugins/{crescendo,tap,graph}.py`, `api/routers/runs.py` | Pass their role when building or calling a connector | FR-7 |
| `backend/myrtia/events/bus.py` | Calls `telemetry.observe_event` after publishing | FR-8 … FR-12 |
| `backend/myrtia/api/routers/metrics.py` (new), `api/app.py` | `GET /metrics`, token gate | FR-1, FR-2 |
| `backend/myrtia/api/routers/metrics.py` | `GET /observability`: dashboard address and whether it answers | FR-21, FR-22, FR-23 |
| `frontend/standalone.html` | "Dashboard" control in the header and its "not running" dialog | FR-20 … FR-23 |
| `observability/grafana/dashboards/myrtia-overview.json`, `compose.observability.yaml` | "Open Myrtia" dashboard link; its address filled in at start from `MYRTIA_URL` | FR-24 |
| `backend/tests_ui/` | `fake_grafana.py`, `features/observability.feature`, steps | FR-20 … FR-22 |
| `compose.observability.yaml`, `observability/` (new) | Prometheus and Grafana, provisioning, dashboard | FR-17, FR-18, NFR-5 |
| `backend/tests/features/observability.feature`, `backend/tests/test_observability.py` (new) | Scenarios and steps | all |
| `docs/observability.md` (new), `README.md`, `AGENTS.md` | How to start and read it | FR-17 |

## Data and state

All state is in memory and lost on restart (FR-3).

```text
counters / gauges:  {metric name: {label tuple: float}}
histograms:         {metric name: {label tuple: [bucket counts…, sum, count]}}
runs seen by events: {run id: (attack, start timestamp)}       # dropped at run.finished
runs with per-run series: ordered {run id: finished?}           # capped, FR-14
```

The run a model call belongs to travels in a `contextvars.ContextVar` set by the
orchestrator and copied into the worker thread that executes the attack.

## Contracts

`GET /metrics` → `200 text/plain; version=0.0.4`. With `MYRTIA_TOKEN` set it needs
`Authorization: Bearer <token>` or `X-Myrtia-Token`; otherwise `401`. The token is not
accepted as a query parameter here.

`GET /observability` → `{"enabled": true, "url": "http://localhost:3000",
"dashboard_url": "http://localhost:3000/d/myrtia-overview/myrtia-overview", "reachable":
false, "start_command": "docker compose -f compose.observability.yaml up -d"}`, or
`{"enabled": false}` when `MYRTIA_GRAFANA_URL` is `off`. `reachable` is one guarded,
short request to the dashboard's health address (SSRF rules, no redirects).

| Metric | Type | Labels |
|---|---|---|
| `myrtia_build_info` | gauge | `version` |
| `myrtia_model_calls_total` | counter | `role`, `model`, `outcome` |
| `myrtia_model_call_duration_seconds` | histogram | `role`, `model` |
| `myrtia_model_tokens_total` | counter | `role`, `model`, `kind` (`prompt`, `completion`) |
| `myrtia_runs_started_total` | counter | `attack` |
| `myrtia_runs_finished_total` | counter | `attack`, `status` |
| `myrtia_runs_active` | gauge | `attack` |
| `myrtia_run_duration_seconds` | histogram | `attack` |
| `myrtia_judge_scores_total` | counter | `attack`, `score` (`0`…`5`, `invalid`) |
| `myrtia_defense_actions_total` | counter | `defense`, `action` |
| `myrtia_events_total` | counter | `type` |
| `myrtia_run_model_calls_total` | counter | `run`, `attack`, `role` |
| `myrtia_run_tokens_total` | counter | `run`, `attack`, `role`, `kind` |
| `myrtia_run_model_seconds_total` | counter | `run`, `attack`, `role` |

Python seams: `telemetry.record_model_call(role, model, ok, seconds, prompt_tokens,
completion_tokens)`, `telemetry.observe_event(event)`, `telemetry.bind_run(run_id,
attack)`, `telemetry.render()`, `telemetry.reset()`. A connector call may pass
`role="…"` to `generate()` to override the connector's own role for that call (the graph
plugin shares one connector between agents of different roles).

Environment: `MYRTIA_METRICS_RUNS` (per-run cap, default 20) and `MYRTIA_GRAFANA_URL`
(where the console's control leads, default `http://localhost:3000`, `off` hides it); for
the stack, `MYRTIA_URL` (where "Open Myrtia" leads, default `http://localhost:8000`),
`MYRTIA_SCRAPE_TARGET` (default `host.docker.internal:8000`), `GRAFANA_PORT` (3000),
`PROMETHEUS_PORT` (9090).

## UI behaviour

The header gets a "Dashboard" chip next to "Demo". On click the console asks
`/observability`: reachable → the dashboard opens in a new tab; not reachable → a dialog
says it is not running, shows the start command with a copy button, and offers "Open
anyway" and "Close". With the address off the chip is hidden. Grafana opens on the provisioned dashboard as an anonymous
viewer; the login form is disabled and both ports bind to `127.0.0.1`.

## Decisions

| Decision | Why | Alternative rejected |
|---|---|---|
| Hand-written registry, no client library | Keeps the runtime dependency-free (NFR-1); the format is small and stable | `prometheus_client`: one more dependency for three metric types |
| Pull metrics at `/metrics` | Standard, works with any collector, nothing to configure in Myrtia | Pushing OTLP: needs a collector address and an SDK |
| Measure in the connector, not in each plugin | Every model call already goes through `generate()`; plugins stay untouched (principle 4) | Instrumenting each plugin: easy to forget in the next one |
| Run metrics derived from the event bus | Events are already the contract (principle 12); no second source of truth | Hooks in the orchestrator: would miss plugin-emitted events |
| Per-run series capped to the most recent runs | A run id as a label is unbounded; the cap keeps the per-run drill-down without the cardinality problem | No run label (loses US-3); unbounded label (grows forever) |
| Role and model as the "agent" dimension | Bounded and meaningful; agent names are free text and stay in the browser | Agent name label: unbounded, and names are not sent to the backend |
| Opt-in Compose overlay | The default install must stay one process (NFR-1) | Adding the services to `compose.yaml`: heavier default |
| Dashboard totals read the counters directly | A counter born with a non-zero value is missed by `increase()`; "since Myrtia started" is exact | `increase()` over the time range: under-counts short runs |
| The server checks whether the dashboard answers | The console's content policy only lets the page talk to its own origin | Probing from the browser: blocked by that policy |
| Dashboard opens in a new tab | A live run view and an unsaved graph stay as they were | Same tab: loses the operator's place |
| Traces left out | Metrics answer the roadmap's questions; traces need an SDK and a store | OpenTelemetry now: larger change, new dependencies |

## Constitution check

- **4, 5 (extension, boundaries):** plugins import nothing new; the connector wrapper and
  the bus hook are the only core touch points. `telemetry` imports nothing from the API.
- **6 (secrets):** labels are role, model, attack, status, score, shield id, event type
  and run id; a scenario asserts no key, header or endpoint reaches the output.
- **7 (outbound requests):** Myrtia makes none; the collector pulls.
- **11 (test-driven):** scenarios first, seen failing, then code.
- **12 (traceable):** no new run behaviour, so no new event; existing events are counted.

## Test strategy

| Requirement | Proof |
|---|---|
| FR-1 | "The metrics address serves the Prometheus text format" |
| FR-2 | "The metrics address follows the access token" |
| FR-3 | Registry starts empty after `reset()` in every scenario's background |
| FR-4, FR-5, FR-6 | "A successful model call is counted with its tokens", "A failed model call is counted as an error", "A reply without usage data records no tokens" |
| FR-7 | "Each caller is labelled with its role" (target, judge, defense, attacker, aux) |
| FR-8, FR-9 | "A run is counted from start to finish", "A finish without a start does not go negative" |
| FR-10 | "Judge verdicts are counted by score" |
| FR-11 | "Shield actions are counted" |
| FR-12 | "Every event is counted by type" |
| FR-13, FR-14 | "Calls inside a run feed its per-run series", "Only the most recent runs keep per-run series" |
| FR-15 | "Secrets and addresses never reach the metrics" |
| FR-16 | "A metrics failure does not break the model call" |
| FR-20, FR-21, FR-22 | UI tier: "The Dashboard control opens the dashboard", "The Dashboard control explains how to start it" |
| FR-21 … FR-23 | "The console is told where the dashboard is", "… when it answers", "The dashboard address can be switched off" |
| FR-24 | "The dashboard links back to the console" |
| FR-17 | Manual: stack started, dashboard seen; "The stack is local and anonymous" checks the Compose file |
| FR-18, FR-19 | "The dashboard only queries exported metrics", "The dashboard has the promised panels" |

## Risks

- **Context not copied into threads a plugin starts itself:** those calls fall back to
  the global metrics only (no per-run series). Accepted; noted in the docs.
- **Docker on Linux cannot reach a server bound to `127.0.0.1`:** documented; run Myrtia
  with `--host 0.0.0.0` behind a firewall or use the full Compose set-up, where the
  collector reaches Myrtia over the Compose network.
- **Dashboard and code drifting apart:** the FR-19 test fails when a query names a
  metric the registry does not declare.
