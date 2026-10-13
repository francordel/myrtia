# Myrtia — architecture (Phase 2)

This document fixes the module boundaries and the one decision that shapes everything
else — the backend language — and defines the interfaces the MVP needs. It is oriented
at the MVP: **CouncilAttack running end-to-end inside Myrtia, driven from the web UI,
with the deliberation shown live** (see `PLANNING.md`, Phase 3).

## Decision D2a — Backend language = Python

**Chosen: Python.** Rationale, decisive:

- CouncilAttack already exists as `plugins/ares-council` in the ARES repo: **2141 lines
  of Python, Apache-2.0**, subclassing `ares.strategies.attack_strategy.AttackStrategy`,
  constructed as `CouncilAttack(config, target_connector)`, driving an
  `ares.connectors.connector.Connector` target, with an in-loop graded 0-5 judge.
- The whole attack surface we want (connectors, strategies, graded judging) is the
  **ARES abstraction layer**, which is Python. Reimplementing it — plus CouncilAttack —
  in Go (PentAGI's language) would be a large rewrite for zero MVP value.
- Myrtia's MVP is defined as an **integration**, not a rewrite. Python lets us host the
  existing plugin directly.

**Consequence for the reference:** PentAGI (Go) is now a **pattern reference only** —
its event-driven orchestration and live-subscription UI model. No Go backend code is
adopted. This keeps us fully clear of the `github.com/vxcontrol/cloud` AGPL landmine
(that dependency is Go/backend; we are not using that backend at all).

## Decision D2b — Transport = FastAPI + WebSocket events (MVP), GraphQL later

- **MVP:** FastAPI REST for run control (`create run`, `get run`, `approve`) + one
  **WebSocket** per run streaming structured events. Lightest path to a live view.
- **Later (Phase 4):** the PentAGI pattern — GraphQL (schema-first) with `graphql-ws`
  subscriptions and Apollo cache auto-update by naming convention — is the scalable
  option if we outgrow raw WS. Documented in `docs/ui-observability-map.md`. Not now.

## Decision D2c — Frontend = React + Vite + TS

Per `docs/ui-observability-map.md`: React 19 + Vite + TypeScript + Tailwind/shadcn.
We reuse the *patterns* (event panels fed by a live stream, token streaming), not
PentAGI's code. Talks to the backend over the run WebSocket + REST.

## Module boundaries

```
myrtia/
  backend/
    myrtia/
      orchestrator/   # runs an attack: wires strategy+target, drives lifecycle, emits events
      plugins/        # attack strategies (ARES-compatible). CouncilAttack adapter first.
      connectors/     # targets: chat API, self-hosted OpenAI-compat, agent endpoint
      judges/         # graded harm judge (0-5), ASR/scoring. (CouncilAttack has its own in-loop.)
      events/         # event schema + in-process bus -> WebSocket fan-out
      hitl/           # PENDING_APPROVAL gate + resolveApproval (our own design)
      store/          # run + result persistence (SQLite for MVP)
      api/            # FastAPI app: REST control + WS stream
  frontend/
    src/              # React live deliberation view, run launcher, approval prompts
```

### 1. Orchestrator
Owns a **run**: given a run spec (attack id + config, target id + config, judge id),
it instantiates the strategy and target connector, executes the strategy lifecycle,
and turns everything into **events** on the bus. It is the only place that knows how to
drive an ARES `AttackStrategy`. It also owns the HITL checkpoints.

### 2. Attack plugins (ARES-compatible)
The plugin contract **is** the ARES one: a class subclassing `AttackStrategy` with
`__init__(config, target_connector)` and `attack()/generate()`, plus a `template()`
descriptor. Myrtia discovers plugins by entry point / registry.

**Vendored (decision, supersedes the earlier "depend, don't fork").** CouncilAttack is
**vendored** into `backend/vendor/ares-council/` (it is our own code, ARES Team,
Apache-2.0) so we can add Myrtia integration seams directly. Two small, additive,
no-op-by-default seams were added and change no existing behaviour or paper numbers:
- `set_event_emitter(emit)` + internal `_emit(type, **payload)` → per-turn live events
  (`goal.started`, `turn.started`, `proposal.created`, `critique.created`,
  `vote.aggregated`, `chairman.synthesized`, `target.responded`, `judge.scored`).
- `load_goals(goals: list[str])` → Myrtia feeds behaviours without an input file.
The plugin emits **primitive `(type, payload)`** and imports nothing from Myrtia, so it
stays reusable; the orchestrator turns each call into a Myrtia `Event`.

### 3. Target connectors
ARES `Connector` implementations. MVP needs one: an **OpenAI-compatible chat connector**
(covers vLLM, Ollama `/v1`, and hosted APIs) — which is exactly what CouncilAttack's
target already is in the experiments. Agent-endpoint connectors come in Phase 4.

### 4. Judges & scoring
Graded harm judge (0-5) against a rubric, plus ASR metrics (matched-budget, Fran's
CouncilAttack judging). CouncilAttack embeds its own in-loop judge, so the MVP mostly
**surfaces** the judge scores it already produces; a standalone judge module is the
generalisation for other attacks.

### 5. Events & observability
A small, typed **event schema** (below) on an in-process async bus, fanned out to the
run's WebSocket. This is the minimum for "see the agents live" — no external infra.
Langfuse (LLM traces/scores) and the OTel->Grafana stack are **opt-in, Phase 4+**.

### 6. Web UI + HITL
React renders the live deliberation from the event stream: council members proposing,
cross-critiques, Borda vote, chairman synthesis, target response, judge score — each
activating as its event arrives. HITL is a **PENDING_APPROVAL** gate (Myrtia's own
design; PentAGI only has conversational steering, per the recon): the orchestrator can
pause before a sensitive step and wait for `resolveApproval` from the UI.

## Event schema (draft, the live-view contract)

One JSON event type per meaningful step. Every event: `run_id`, `seq`, `ts`, `type`,
`payload`. Types for the CouncilAttack MVP:

- `run.started` / `run.finished` — spec, final status, summary ASR
- `goal.started` — the behaviour being attacked
- `turn.started` — turn index
- `proposal.created` — `{model, mutator, proposal, template}` (one per council member)
- `critique.created` — `{critic, rankings, reasons}`
- `vote.aggregated` — `{borda_scores, top1_votes, winner}`
- `chairman.synthesized` — `{synthesized_prompt}`
- `target.responded` — `{target_prompt, target_response}`
- `judge.scored` — `{score 0-5, rationale}`
- `approval.requested` / `approval.resolved` — HITL
- `log` — free-text, for anything unmapped

The UI needs nothing beyond this to render the deliberation. This schema also fixes the
**key MVP integration question** (below).

## The key MVP risk — tapping the deliberation live

CouncilAttack produces rich per-turn structured records (`proposals[]`, `critiques[]`,
`winner`, `synthesized_prompt`, `judge_score`) — the same fields saved to
`council_attacks.json`. To show them *live* rather than only at the end, the
orchestrator must **observe the strategy mid-run** without forking its 2141 lines.
Options, in order of preference:

1. **Callback/emitter injected via config** — if the strategy already exposes a logging
   or progress hook we can subscribe to (to confirm by reading `council_attack.py`).
2. **Logging tap** — attach a handler to the strategy's logger and map log records to
   events. Non-invasive, but brittle (parses log lines).
3. **Small upstream PR to `ares-council`** — add an optional `on_event` callback to the
   strategy. Clean, reusable, and we own the plugin. Preferred if (1) does not exist.

**Resolved (read `council_attack.py`, 2141 lines):** there is **no callback/`on_event`
hook** — the plugin uses stdlib `logging` (`logger = logging.getLogger(__name__)`) with
rich per-step INFO lines, and writes a **per-goal structured checkpoint** to
`self._output_path` (`council_attacks.json`, full `proposals/critiques/winner/
synthesized_prompt/judge_score`). So:

- **Bootstrap (thin slice):** tail the per-goal checkpoint JSON → emit structured events
  at **goal** granularity. Zero plugin changes; enough to prove the loop in the UI.
- **Target (chosen seam):** **Option 3** — add an optional `on_event(event)` callback to
  `CouncilAttack` (we own `ares-council`, Apache-2.0). Gives **per-turn** structured
  events (proposal/critique/vote/chairman/judge) with no log-parsing. This is the one
  small upstream change Myrtia needs; everything else is integration.

First Phase 3 tasks, in order: (a) OpenAI-compat connector + a smoke run of the vendored
plugin against a local Ollama `/v1`; (b) add `on_event` to the plugin; (c) map events →
WS → React panels.

## What we are NOT doing
- No Go backend, no PentAGI code, nothing importing `github.com/vxcontrol/cloud`.
- No GraphQL, no Grafana/Jaeger/Loki/Langfuse for the MVP (all Phase 4+ opt-in).
- No breadth: one attack (CouncilAttack), one connector (OpenAI-compat), one judge.
