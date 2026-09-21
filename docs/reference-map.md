# PentAGI reference map (for Myrtia)

Reconnaissance of the PentAGI Go backend (`backend/`) as a *pattern* reference for
Myrtia. Nothing here is copied code; this documents how PentAGI is built so we can
decide what pattern to reimplement and what to avoid. Myrtia is an **AI/LLM
red-teaming** framework (jailbreaks, prompt injection, multi-turn priming, unsafe agent
behaviour), not a network pentest tool. The entire PentAGI *pentest* layer (Kali images,
exploit/command execution, the ~200 security tools, the attack sandbox) is therefore
out of scope and is only noted here to be discarded.

Source read: `backend/pkg/*`, `backend/cmd`, `backend/go.mod`, `backend/go.sum`,
`gqlgen.yml`, `migrations/`. Read-only; nothing in the reference repo was modified.

---

## TASK 1 — Architecture map of the reusable scaffolding

### 1.1 The orchestration loop (flows -> tasks -> subtasks -> actions)

PentAGI models work as a four-level hierarchy, each level persisted in Postgres and
each with its own "worker" goroutine and controller:

- **Flow** — the top-level session. `pkg/controller/flow.go` defines `FlowWorker`
  (interface) and `flowWorker` (impl). A flow owns a set of tasks and a set of
  *assistants* (interactive chat sessions), guards them with a mutex + `sync.WaitGroup`,
  and exposes `PutInput`, `WaitTaskCompletion`, `AddAssistant`, `InvalidateTaskSubtasks`.
  It wires together a bundle of per-flow log workers (`flowProviderWorkers`:
  message log, agent log, search log, terminal log, vector-store log, tool-call log,
  screenshot). This bundle is the backbone of the live UI streaming.
- **Task** — `pkg/controller/task.go` / `tasks.go`. A user input becomes a task.
- **Subtask** — `pkg/controller/subtask.go` / `subtasks.go`. The planner decomposes a
  task into an ordered list of subtasks.
- **Action** — an individual LLM tool call executed while working a subtask.

The planning cycle is driven from `pkg/providers/provider.go`:
- **Generator** (`OptionsTypeGenerator` / `PromptTypeSubtasksGenerator`) turns a task
  into subtasks.
- **Refiner** (`OptionsTypeRefiner`) re-plans remaining subtasks as execution reveals
  new facts.
- **Reporter** (`PromptTypeReporter` / `PromptTypeTaskReporter`) writes up results.
- Prompt rendering has size guards (`msgGeneratorSizeLimit` 150 KB, `msgRefinerSizeLimit`
  / `msgReporterSizeLimit` 100 KB); if a rendered prompt exceeds the cap the code trims
  the history window and re-renders. This is a cheap, deterministic pre-LLM context guard
  worth copying.

**Delegation model — subagents are exposed to the primary agent as tools.** There is a
"primary agent" (`OptionsTypePrimaryAgent`) and roughly a dozen specialist agent roles,
enumerated in `pkg/providers/pconfig/config.go` (`ProviderOptionsType`) and mirrored 1:1
in `pkg/templates` (`PromptType*`):

  `primary_agent, assistant, simple, simple_json, adviser, generator, refiner,
  searcher, enricher, coder, installer, pentester, reflector` (plus a memorist role and
  question-* variants used for the graph/memory queries).

The orchestrator does **not** hand off with a bespoke router. Instead each subagent is
published as a **function/tool** on the primary agent's executor. `pkg/providers/handlers.go`
builds handler closures — `GetAskAdviceHandler`, `GetCoderHandler`, `GetInstallerHandler`,
`GetMemoristHandler`, `GetPentesterHandler`, `GetSubtaskSearcherHandler`,
`GetTaskSearcherHandler` — each returning a `tools.ExecutorHandler`. When the primary
agent calls e.g. the "coder" tool, the handler renders that subagent's own prompt, runs
its own LLM chain, and returns the result string as the tool result. Sub-agents can be
compositional (the advice handler internally runs an *enricher* pass, then an *adviser*
pass). **This "subagent-as-tool" pattern is the single most reusable idea** and maps
cleanly onto Myrtia (attack-technique agents, a judge agent, a target-probe agent all
as tools of an orchestrator).

### 1.2 Tool-call limits and the Reflector (graceful termination)

Defined in `pkg/providers/performer.go`. The core loop `performAgentChain` runs an agent's
tool-calling chain with hard iteration ceilings:

- `maxGeneralAgentChainIterations = 100` (primary/long-running agents)
- `maxLimitedAgentChainIterations = 20` (bounded subagents — this is the
  "MAX_LIMITED_AGENT_TOOL_CALLS" concept)
- `maxReflectorCallsPerChain = 3`, `maxAgentShutdownIterations = 3`
- retry ceilings: `maxRetriesToCallSimpleChain/AgentChain/Function = 3`,
  `delayBetweenRetries = 5s`, plus `maxSoftDetectionsBeforeAbort = 4`.

The **Reflector** (`OptionsTypeReflector`, `performReflector` / `performCallerReflector`)
is a graceful-termination mechanism: as an agent approaches its tool-call ceiling, the
loop injects a reflector turn that asks the model to wrap up and call a **barrier tool**
(a terminal tool such as "report result" — see `Barrier` in `provider.go` and
`IsBarrierFunction` / `GetBarrierToolNames` / `GetBarrierTools` on the executor). This
converts "ran out of budget" into a clean, structured final answer instead of a hard cut.
For Myrtia this is directly useful: cap an attack agent's turns and force a scored
verdict via a barrier tool.

### 1.3 Context / chain summarization (`pkg/csum`)

`pkg/csum/chain_summary.go` implements chain compaction so long agent histories stay
under the model window. The message chain is split into **sections** (`cast.NewChainSection`,
`pkg/cast`) of question/answer (tool-call + tool-result) pairs. Key tunables:

- keep the last section verbatim (`preserveAllLastSectionPairs`), cap it at
  `maxLastSectionByteSize = 50 KB` with a 25% reserve for future messages;
- any single body pair over `maxSingleBodyPairByteSize = 16 KB` is summarized in place
  via an LLM call (`PromptTypeSummarizer`), replacing the pair with a
  `cast.Summarization` marker (`**summarized content:**`);
- optional QA-pair summarization (`useQAPairSummarization`, `maxQAPairSections = 10`,
  `maxQAPairByteSize = 64 KB`);
- special handling to preserve/fake reasoning signatures on summarized tool calls so
  providers that require them (reasoning models) don't break.

This is a self-contained, provider-agnostic algorithm — a strong KEEP-candidate pattern.

### 1.4 LLM provider integration (`pkg/providers`)

Abstraction is over a **forked langchaingo** (`github.com/vxcontrol/langchaingo`, the
`llms` package) plus a PentAGI `Provider` interface (`pkg/providers/provider.go`).

- Concrete providers, one subpackage each: `anthropic, openai, openaicompat, bedrock,
  gemini, deepseek, ollama, custom, glm, kimi, minimax, qwen`, plus `embeddings`.
  A `registry.go` registers them; `pconfig` holds per-provider, per-agent-type model
  and call-option config (`GetOptionsForType`, `PrepareAdaptiveCallOptions`, temperature,
  streaming, JSON mode, reasoning options).
- The `Provider` interface exposes `Model(optType)`, `Executor()`, and the `Get*Handler`
  subagent factories. Each agent role can be pointed at a **different model** — e.g. a
  cheap model for the searcher, a strong model for the primary agent.
- **Function calling** is uniform through langchaingo's `llms.ToolCall` /
  `MessageContent` / streaming types; tool schemas come from `invopop/jsonschema`.
  Retries, streaming, and reasoning-content handling are centralised in `performer.go`.

For Myrtia we want the *shape* of this (a `Provider` interface + per-role model
routing + a uniform tool-call abstraction) but should build it on the **upstream**
`tmc/langchaingo` or a thin in-house client, not the vxcontrol fork by default (see
Task 2).

### 1.5 Memory / state / context

Three stores, layered:

- **PostgreSQL (primary state)** via `sqlc`-generated code in `pkg/database` (see
  `querier.go`, `models.go`, the `*.sql.go` files) and `pressly/goose` migrations in
  `backend/migrations/sql` (`20241026_..._initial_state.sql` onward). Everything durable
  — flows, tasks, subtasks, message logs, agent logs, tool-call logs, screenshots,
  assistants — lives here.
- **pgvector (semantic memory)** via `pgvector/pgvector-go` + `jackc/pgx/v5`. The
  `pkg/database/knowledge` package and `vecstorelogs` hold embeddings for
  retrieval-augmented memory; embeddings come from `pkg/providers/embeddings`.
- **Graphiti / temporal knowledge graph (Neo4j-backed)** via `pkg/graphiti`, a thin
  wrapper (`client.go`) that re-exports types from `github.com/vxcontrol/graphiti-go-client`
  and talks to a separate Graphiti service (see repo-root `docker-compose-graphiti.yml`).
  It offers temporal / entity-relationship / diverse / episode-context / "successful
  tools" / recent-context searches — i.e. long-term episodic memory of what worked. A
  `memorist` subagent queries it. `pkg/graphiti` is feature-flagged (`enabled bool`) and
  **does not import vxcontrol/cloud** — it is cleanly separable.

For Myrtia, Postgres+pgvector is a solid KEEP-pattern; the Graphiti graph is
optional and heavyweight (extra service + Neo4j) — reasonable to defer or replace.

### 1.6 Server / API (`pkg/server`, `pkg/graph`)

- **GraphQL via gqlgen** (`99designs/gqlgen`, `vektah/gqlparser`). Schema in
  `pkg/graph/schema.graphqls`, generated code in `pkg/graph/generated.go`, resolvers in
  `schema.resolvers.go`, config in `gqlgen.yml`. **Subscriptions** (`pkg/graph/subscriptions`)
  stream live flow/task/log/screenshot updates to the React frontend over websockets —
  this is how the UI shows agent progress in real time. The per-flow log workers from
  1.1 feed these subscriptions.
- **HTTP layer** is Gin (`gin-gonic/gin`) in `pkg/server/router.go` with CORS, sessions,
  static serving, Swagger docs (`pkg/server/docs`), OAuth (`pkg/server/oauth`, OIDC),
  local auth (`pkg/server/auth`), and services (`pkg/server/services`).
- **Note:** `router.go` and `services/graphql.go` / `services/anonymizer.go` import the
  AGPL `vxcontrol/cloud` anonymizer to scrub PII from prompts/telemetry. That coupling is
  narrow and removable (see Task 2).

The GraphQL-subscriptions-driven live UI is a good pattern to reimplement; Myrtia
could equally use it or a simpler websocket/SSE event stream.

---

## TASK 2 — Licence audit (critical)

**Finding on `github.com/vxcontrol/cloud` (AGPL-3.0, no usable exception for us):** it is
imported **only** for one feature — the PII **anonymizer** (`.../cloud/anonymizer` and
`.../cloud/anonymizer/patterns`) plus `.../cloud/sdk` referenced in config. Direct source
importers (verified by grep):

- `pkg/config/config.go` (`anonymizer/patterns`, `sdk`)
- `pkg/graph/resolver.go` (`anonymizer`)
- `pkg/server/router.go`, `pkg/server/services/graphql.go`,
  `pkg/server/services/anonymizer.go` (`anonymizer`)
- `pkg/tools/{tools,code,guide,search}.go` (`anonymizer`)
- `cmd/ftester/worker/executor.go`, `cmd/installer/hardening/hardening.go`,
  `cmd/installer/wizard/models/server_settings_form.go`

Because `pkg/config` imports it and nearly every package imports `pkg/config`, the
*shipped binary* transitively links AGPL code across almost the whole backend. **But the
actual code coupling is tiny** — a PII scrubbing helper. Severing it (replace with an
in-house/permissive anonymizer or a no-op) de-taints the entire tree. So the taint below
is "links AGPL as built", not "this package's logic is AGPL".

### Per-package classification (`backend/pkg/*` and `backend/cmd`)

Legend: **AVOID (AGPL)** = imports `vxcontrol/cloud` in its own source; **AVOID*
(transitive)** = clean source but links cloud only via `pkg/config`/`pkg/tools` etc.
(de-taints once the anonymizer is removed); **KEEP-CANDIDATE** = MIT-clean and reusable;
**IGNORE** = out-of-scope pentest layer.

| Package | Classification | Reason |
|---|---|---|
| `pkg/config` | **AVOID (AGPL)** — de-taintable | imports `cloud/anonymizer/patterns` + `cloud/sdk`; otherwise a generic env-config pattern worth reimplementing without cloud |
| `pkg/graph` | **AVOID (AGPL)** — de-taintable | `resolver.go` imports `cloud/anonymizer`; rest is gqlgen scaffolding (KEEP-pattern) |
| `pkg/server` | **AVOID (AGPL)** — de-taintable | router + services import `cloud/anonymizer`; Gin/OAuth/subscriptions scaffolding is KEEP-pattern once anonymizer is swapped |
| `pkg/tools` | **IGNORE** (also AGPL) | pentest tool executors (code exec, guide, search, terminal, security tools) — out of scope; also imports cloud |
| `pkg/controller` | **KEEP-CANDIDATE** (AVOID* as-built) | flow/task/subtask orchestration — the pattern we want; clean source, links cloud only via config/graph/tools |
| `pkg/providers` | **KEEP-CANDIDATE** (AVOID* as-built) | LLM abstraction + subagent handlers; clean of cloud in source but built on the vxcontrol/langchaingo fork and imports config/tools |
| `pkg/csum` | **KEEP-CANDIDATE** (AVOID* as-built) | context summarization algorithm; clean source, imports cloud only via `pkg/tools` types |
| `pkg/cast` | **KEEP-CANDIDATE** (AVOID* as-built) | message-chain / section data model; via `templates`->`tools` |
| `pkg/templates` | **KEEP-CANDIDATE** (AVOID* as-built) | prompt templates + renderer; via `tools` |
| `pkg/database` | **KEEP-CANDIDATE** (AVOID* as-built) | sqlc + pgvector persistence; clean source, via config/tools |
| `pkg/graphiti` | **KEEP-CANDIDATE** | temporal knowledge-graph client; **no cloud import**; depends only on `vxcontrol/graphiti-go-client` (verify licence) |
| `pkg/observability` | **KEEP-CANDIDATE** (AVOID* as-built) | OTel + Langfuse wiring; via config |
| `pkg/schema` | **KEEP-CANDIDATE (clean)** | pure schema types, no internal imports, no cloud |
| `pkg/resources` | **KEEP-CANDIDATE (clean)** | embedded resources, no cloud |
| `pkg/version` | **KEEP-CANDIDATE (clean)** | version info, no cloud |
| `pkg/system` | **KEEP-CANDIDATE** (AVOID* as-built) | host/system info; via config |
| `pkg/csum`,`pkg/cast` | (above) | |
| `pkg/docker` | **IGNORE** | docker attack-sandbox management — out of scope |
| `pkg/flowfiles` | **IGNORE** (borderline) | file transfer into the attack container (depends on `pkg/docker`); generic file handling but tied to sandbox |
| `pkg/terminal` | **IGNORE** | pty/terminal into attack container — out of scope; clean source though |
| `cmd/pentagi` | **AVOID* as-built** | main binary; wires everything incl. config -> cloud |
| `cmd/ctester` | **KEEP-CANDIDATE** (AVOID* as-built) | provider tester harness; useful pattern; via config |
| `cmd/etester` | **KEEP-CANDIDATE** (AVOID* as-built) | embeddings tester; via config |
| `cmd/ftester` | **IGNORE / AVOID (AGPL)** | flow/tool tester; `worker/executor.go` imports cloud directly; tied to pentest tools |
| `cmd/installer` | **AVOID (AGPL)** + IGNORE | installer wizard imports cloud directly; product-specific, not needed |

### Other vxcontrol dependencies in `backend/go.mod`

Modules are **not present in the local module cache** and `go` is not installed in this
environment, so exact licence files could not be read from disk (`go.sum` only carries
hashes, not licences). Best determination:

| Module | Version | Classification | Reason / how to confirm |
|---|---|---|---|
| `github.com/vxcontrol/cloud` | v0.9.0 | **AVOID (AGPL-3.0)** | AGPL-3.0 with an exception granted only to official PentAGI; confirmed by task brief. Do not use. Only powers the PII anonymizer — trivially replaceable. |
| `github.com/vxcontrol/langchaingo` | v0.1.14-update.7 | **KEEP-CANDIDATE — verify on GitHub** | Fork of `github.com/tmc/langchaingo`, which is **MIT**. A fork almost certainly keeps MIT, but confirm the LICENSE at github.com/vxcontrol/langchaingo before adopting. Even so, prefer building on **upstream `tmc/langchaingo`** (or a thin in-house client) to avoid a single-vendor fork and any hidden cloud coupling. |
| `github.com/vxcontrol/graphiti-go-client` | v0.9.0 | **KEEP-CANDIDATE — verify on GitHub** | Thin REST client for the Graphiti service; likely MIT/Apache but **unconfirmed** — read LICENSE at github.com/vxcontrol/graphiti-go-client before use. Graphiti itself (the Python service) is Apache-2.0. Only needed if we adopt the graph-memory feature. |

**Rule for Myrtia (already in PLANNING.md):** nothing importing `vxcontrol/cloud`
enters the repo. In practice that means: do not lift `pkg/config`, `pkg/graph`,
`pkg/server`, `pkg/tools`, `cmd/installer`, or `cmd/ftester` source as-is; reimplement
the config/GraphQL/server *patterns* without the anonymizer import, and drop `pkg/tools`
entirely (out of scope). Provide our own PII scrubbing (permissive lib or in-house) if we
want that feature.

---

## Recommendation — reimplement vs rewrite

**Reimplement the pattern (high value, clean to redo):**

1. **Orchestrator + subagent-as-tool delegation** (from `pkg/controller` +
   `pkg/providers/handlers.go`): flow -> task -> subtask -> action hierarchy, each
   subagent exposed as a tool on the primary agent, per-role model routing. This is the
   heart of the value and maps directly to Myrtia's attack/target/judge agents.
2. **Bounded agent loop with a Reflector + barrier tools** (from `pkg/providers/performer.go`):
   hard iteration caps (general vs limited), retry/backoff, and graceful termination that
   forces a structured final verdict. Ideal for capping an attack agent and forcing a
   scored result.
3. **Context/chain summarization** (from `pkg/csum`): section-based compaction with
   byte-size thresholds and reasoning-signature preservation. Provider-agnostic; reusable
   almost verbatim as a design.
4. **Live UI event streaming** (from `pkg/graph/subscriptions` + per-flow log workers):
   GraphQL subscriptions (or a simpler SSE/websocket bus) fed by typed log workers, for
   the human-in-the-loop UI with real-time agent traces.

**Rewrite from scratch / build fresh:**

- **Provider layer** — keep the `Provider` interface + per-role model config *shape*, but
  build on upstream `tmc/langchaingo` or a small in-house client. Avoid the vxcontrol
  langchaingo fork by default.
- **Config, GraphQL server, auth/OAuth** — reimplement cleanly (gqlgen + Gin patterns are
  fine) with **no** `vxcontrol/cloud` anonymizer import.
- **Persistence** — reuse the sqlc + goose + pgvector *approach*; write our own schema for
  red-teaming (runs, techniques, targets, transcripts, judge scores).

**Discard entirely (out of scope):** `pkg/tools`, `pkg/docker`, `pkg/terminal`,
`pkg/flowfiles`, the Kali/attack-sandbox layer, `cmd/ftester`, `cmd/installer` — all
network-pentest specific, and several also carry the AGPL import.

**Optional / defer:** the Graphiti temporal knowledge graph (`pkg/graphiti` + Neo4j
service). Powerful episodic memory, but heavy infra; pgvector alone likely covers
Myrtia's MVP memory needs.
