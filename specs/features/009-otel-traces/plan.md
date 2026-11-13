# Plan 009 — Run traces with OpenTelemetry

> How the spec will be built. Read `specs/constitution/` and this feature's `spec.md`
> first. Every part names the requirements it covers.

## Approach

A new module, `myrtia.tracing`, turns what spec 008 already taps into spans: the event
bus gives the structure (run, goal, turn, and the events inside them) and the connector
wrapper gives the model calls. Parents are set explicitly from a per-run stack of open
spans, found through the run already bound to the worker's context in 008, so no
OpenTelemetry context is attached or detached across threads. The OpenTelemetry SDK is an
optional extra, imported only when tracing is switched on. Spans leave through the
standard OTLP/HTTP exporter in the background. The optional stack gains Tempo as the
trace store and a second Grafana dashboard.

## Affected areas

| Area | Change | Covers |
|---|---|---|
| `backend/myrtia/tracing.py` (new) | Configuration, span stack per run, `observe_event`, `start_model_call`, content rules, `status`, `shutdown` | FR-1 … FR-15 |
| `backend/myrtia/connectors/base.py` | The `observed` wrapper also opens and closes a model-call span | FR-7, FR-15 |
| `backend/myrtia/events/bus.py` | Calls `tracing.observe_event` after publishing | FR-5, FR-6, FR-8 … FR-10 |
| `backend/myrtia/api/routers/metrics.py`, `api/app.py` | `/observability` reports tracing; spans flushed at shutdown | FR-4 |
| `backend/pyproject.toml` | `otel` extra (SDK and OTLP/HTTP exporter), included in `dev` | NFR-1 |
| `compose.observability.yaml`, `observability/tempo/`, `observability/grafana/` | Tempo, its data source, the "Myrtia traces" dashboard, links between dashboards | FR-16 … FR-18 |
| `backend/tests/features/tracing.feature`, `backend/tests/test_tracing.py` (new) | Scenarios and steps | all |
| `docs/observability.md`, `README.md`, `AGENTS.md`, roadmap | How to switch it on and read it | FR-2, FR-17 |

## Data and state

In memory, per run: the root span and a stack of open spans (`run` → `goal` → `turn`).
Nothing is stored by Myrtia; finished spans go to the exporter. In the stack, Tempo keeps
them in a Docker volume (30 days), outside the repository.

```text
run graph                      myrtia.run.id, myrtia.attack, myrtia.target.model, …
└─ goal 0                      myrtia.goal.index, myrtia.goal
   └─ turn 1                   myrtia.turn, myrtia.judge.score
      ├─ chat qwen2.5:3b       myrtia.role=attacker, gen_ai.*, tokens, messages
      ├─ event proposal.created
      ├─ chat gemma3:1b        myrtia.role=target
      └─ event judge.scored
```

## Contracts

Environment (all read by Myrtia):

| Variable | Default | Meaning |
|---|---|---|
| `MYRTIA_TRACES` | `off` | `on` switches tracing on |
| `MYRTIA_OTEL_ENDPOINT` | `http://localhost:4318` | OTLP/HTTP base address (`/v1/traces` is appended) |
| `MYRTIA_TRACE_CONTENT` | `on` | `off` leaves prompts, replies and event text out |
| `MYRTIA_TRACE_MAX_CHARS` | `20000` | Longest piece of content kept |

Span attributes: `gen_ai.operation.name` (`chat`), `gen_ai.request.model`,
`gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.input.messages`,
`gen_ai.output.messages` (JSON text; content only), `error.type`; and `myrtia.run.id`,
`myrtia.attack`, `myrtia.role`, `myrtia.goal.index`, `myrtia.turn`,
`myrtia.judge.score`, `myrtia.run.status`, `myrtia.content.truncated`. Event payload
fields become `myrtia.<field>` attributes of the span event.

`GET /observability` gains `"tracing": {"enabled": bool, "reason": str}`.

Python seams: `tracing.observe_event(event)`, `tracing.start_model_call(role, model,
prompt)` → handle with `.end(ok, error, response, prompt_tokens, completion_tokens)` or
`None`, `tracing.status()`, `tracing.shutdown()`, and for tests `tracing.use_exporter()`
and `tracing.reset()`.

## UI behaviour

No change to the console. Grafana gets "Myrtia traces": a table of recent runs (attack,
start, duration) whose trace id opens the same dashboard on that trace, and a timeline
panel for the selected trace. Both dashboards link to each other and to the console.

## Decisions

| Decision | Why | Alternative rejected |
|---|---|---|
| Spans built from the bus and the connector wrapper | Same two taps as 008: plugins need no tracing code (principle 4) | Tracing calls inside every plugin |
| Explicit parents from a per-run stack | Events arrive from the server loop and from worker threads; attaching context across threads fails | `context.attach` per event |
| Private tracer provider, not the global one | Myrtia must not capture or alter spans of libraries the operator runs alongside | Setting the global provider |
| SDK as an optional extra, off by default | NFR-1 and FR-1: the default install and behaviour stay as they are | Hard dependency |
| OTLP over HTTP | One small exporter, no gRPC toolchain | OTLP/gRPC |
| Full content by default, with an off switch | Maintainer's decision: runs must be auditable; some deployments will want structure only | Content off by default |
| Keys scrubbed even with content on | Principle 6 is not negotiable; an audit does not need credentials | Raw content |
| Tempo as the store | Reads OTLP natively, single binary, native Grafana data source, links with the metrics dashboard | Jaeger: second UI outside Grafana |
| Every run traced, no sampling | Audit needs completeness; volumes are small | Probabilistic sampling |

## Constitution check

- **4, 5:** plugins untouched; `tracing` imports nothing from the API layer.
- **6:** keys and headers never become attributes; content passes the same scrubber the
  run store uses; a scenario asserts it.
- **7:** the export address is checked against the SSRF rules before use.
- **8:** trace data lives in a Docker volume; nothing is written under the repository;
  `observability/` stays out of the application image.
- **11:** scenarios first, seen failing.
- **12:** this is the feature that makes "traceable by default" inspectable outside the
  console; no run behaviour changes, so no new event.

## Test strategy

| Requirement | Proof |
|---|---|
| FR-1 | "Tracing is off by default" |
| FR-2, FR-3, FR-4 | "Tracing reports where it exports", "Missing packages do not stop Myrtia", "A blocked address switches tracing off", "The console is told whether tracing is on" |
| FR-5, FR-6, FR-7, FR-9 | "A run becomes one trace of nested steps", "A model call records role, model, tokens and outcome", "A failed run marks its trace as an error", "A single-shot run hangs its calls under the run" |
| FR-8, FR-10 | "Events are attached to the step they happened in", "The verdict is recorded on the turn" |
| FR-11, FR-12, FR-14 | "Content is included by default", "Content can be switched off", "Long content is cut and marked" |
| FR-13 | "Keys never reach a trace" |
| FR-15 | "A tracing failure does not break the model call" |
| FR-16 | "Trace data stays out of the repository and the image" |
| FR-17, FR-18 | "The stack has a local trace store", "The traces dashboard lists runs and shows one", manual check |

## Risks

- **Convention drift:** the generative-AI conventions are still marked as in development;
  attribute names may change. They are constants in one module.
- **Harmful text in traces:** by design (audit). Contained by FR-16 and by the store
  being bound to the local machine.
- **Sequential assumption:** the per-run stack assumes one goal and one turn open at a
  time, which holds for every bundled attack.
