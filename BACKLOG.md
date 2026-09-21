# Myrtia — backlog

Living task board, organised in sprints. Claude maintains this: when we talk, new
items get added here and picked up. Rule: there should always be one task in progress.
Status: ✅ done · 🚧 in progress · ⬜ todo.

> Once the repo is on GitHub, these can mirror to GitHub Issues / Projects (or Linear)
> for a visual board. For now this file is the single source of truth.

## Sprint 0 — Foundations ✅
- ✅ Name (working: Myrtia) · Apache-2.0 licence · architecture doc
- ✅ Vendored `ares-council` with `on_event` + `load_goals` seams

## Sprint 1 — MVP + UX ✅
- ✅ Backend: event bus, orchestrator, connectors, HITL stub, store, FastAPI + WS
- ✅ Live deliberation UI (zero-build standalone + Vite scaffold)
- ✅ Attacks selectable: `council`, `council-crescendo`, `direct` (+ per-attack config schema)
- ✅ Run history: search + filter by goal / theme / result / evaluation
- ✅ Behaviour library (HarmBench 278) with per-theme checkboxes + search
- ✅ Google Threat Intelligence theme (dark default + light toggle), responsive
- ✅ Voting panel (proposals + Borda table + critic rankings); goal/turn collapsibles; read-more; stats dashboard
- ✅ Frontier auth (OpenAI + Anthropic OpenAI-compat) + API-key redaction in API responses
- ✅ Real experiment vs claude-sonnet-5 (finding: Claude refuses to be an attacker → open-model council needed)

## Sprint 2 — Models, providers & attacks 🚧
- 🚧 Pull open council models (llama3.2:3b, gemma2:2b) + relaunch demo with permissive 3-model council
- ⬜ API keys in the UI (paste key per provider; provider presets OpenAI/Anthropic/Ollama/vLLM)
- ⬜ Dynamic model lists: query `/v1/models` (OpenAI/Anthropic) + `/api/tags` (Ollama) → populate dropdowns (never outdated) + billing links
- ⬜ Download local models from the UI (Ollama pull); (later) browse HuggingFace
- ⬜ Integrate more ARES attacks (echo-chamber, tap, autodan, gcg, human-jailbreak, pyrit) as plugins
- ⬜ Per-attack info tab (paper link + how-it-works diagram), GTI-style

## Sprint 3 — Navigation & analytics ⬜
- ⬜ Left sidebar nav (New run · History · Behaviours · Attacks · Models & keys · Dashboard)
- ⬜ ASR-by-theme dashboard computed per-goal (not just per-run)
- ⬜ Export run results (CSV / JSON)
- ⬜ HITL approval UI (PENDING_APPROVAL gate wired end-to-end)

## Review findings (3 audit agents, 2026-09-22)

### Fixed ✅
- ✅ CRITICAL: api_key leaked over WebSocket in RUN_STARTED (redacted now)
- ✅ Raw tracebacks streamed to UI (now logs-only + clean message)
- ✅ Frontend XSS via innerHTML (model/theme/critic/etc. now escaped)
- ✅ Duplicate id=theme (theme tag was never captured) → #themeTag
- ✅ Live re-render wiped collapse/read-more state → persisted
- ✅ No WS reconnect → auto-reconnect w/ backoff
- ✅ Launch: res.ok/run_id guards, empty-goal block, button disable

### Remaining bugs ⬜
- ⬜ [HIGH] Open CORS (`*`) + no auth on backend → add local token/origin gate
- ⬜ [MED] Fire-and-forget run task can be GC'd → keep task refs
- ⬜ [MED] WS poll loop can spin forever if run dies pre-RUN_FINISHED → break on terminal status
- ⬜ [MED] Unbounded in-memory growth (backlog/store) + O(n) backlog copy per poll → cap/evict + index slice
- ⬜ [MED] hitl approvals Future bound to wrong loop (latent until wired) → loop.create_future

### New proposals from product review ⬜
- ⬜ Durable persistence (SQLite behind RunStore) — history/stats survive restart (biggest credibility gap)
- ⬜ Cancel/stop a running attack (+ hard timeout) — top live-demo risk
- ⬜ Cost & token accounting per run ($ estimate) — buyers ask "what does a run cost?"
- ⬜ Connectivity preflight ("test connection" before launch)
- ⬜ Per-run narrative report export (HTML/PDF) — the thing you send a boss
- ⬜ Reproducibility metadata (seed, model versions, config hash) per run
- ⬜ Structured error cards (classify auth/model-not-found/timeout/refusal)
- ⬜ Guardrail / defence-panel eval mode (Fran's differentiator)
- ⬜ Live progress / ETA (goals done / total, elapsed)
- ⬜ Tests (backend + frontend) — zero today

## Backlog (later) ⬜
- ⬜ GraphQL + subscriptions (scale beyond raw WS)
- ⬜ More target connectors (agent endpoints, guarded connectors)
- ⬜ Benchmark / leaderboard; contributor docs; public launch
- ⬜ Name clearance (trademark/domain) before going public
