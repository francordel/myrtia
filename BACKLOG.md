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
- ✅ Integrate the ARES attack strategies as plugins. Black-box, end-to-end verified:
  `direct`, `human-jailbreak`, `obfuscation` (now the full ARES/garak Encoding family:
  base64/base32/base16/hex/ascii85/uu/ROT13/Morse/NATO/Braille/binary/leetspeak/reversed/
  atbash/quoted-printable/zalgo/unicode-tag), `crescendo` (ARES/PyRIT dual-LLM multi-turn
  escalation), plus Myrtia's own `council` / `council-crescendo` / `payload-splitting`.
- ✅ Integrate the NVIDIA garak black-box probes as plugins (end-to-end verified):
  `promptinject` (goal hijacking), `grandma` (emotional framing), `smuggling` (hypothetical /
  function masking), `phrasing` (past/future tense), `latent-injection` (indirect injection in
  a benign doc), and `tap` (TAP / PAIR adaptive attacker+judge loop, width 1 = PAIR). 13
  attacks total now.
- ⬜ [white-box] `gcg` (Greedy Coordinate Gradient) + `autodan`: ARES/garak ship these but they
  need model weights + gradients (GPU), so they are NOT black-box compatible and cannot run
  against an API target. Add only behind a HuggingFace/white-box target connector; until then
  they stay out of the runnable registry (would never complete end-to-end otherwise).
- ⬜ [needs a special target/sink] remaining garak probes that do not fit a plain chat API:
  `visual_jailbreak` (needs a vision-language target), `web_injection` / `exploitation`
  (markdown/XSS/SQL/Jinja — need a rendering or execution sink downstream), `atkgen` (needs a
  fine-tuned toxic-prompt generator), `glitch` / `dra` (tokenizer-specific), `ansiescape`
  (terminal control codes). Port when Myrtia grows the matching connector types.
- ⬜ **Upload your own behaviour dataset** (like HarmBench): let the operator upload a file of
  goals instead of only the bundled HarmBench 278. Requirements shown in the UI: a parseable
  format — CSV in the HarmBench shape (a `Behavior` column, comma-separated, one goal per row;
  optional `SemanticCategory`/`context`), or one goal per line for plain `.txt`. Validate on
  upload (reject unparseable/oversized files, cap row count), preview parsed goals, then feed
  them to any attack as a custom theme.
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

## Security review (3 audit agents, 2026-09-22)

### Fixed ✅
- ✅ SSRF/metadata: block link-local (169.254.x) + metadata hosts on /chat, /chat/stream, target connector, and council model calls (loopback/LAN still allowed — legit targets)
- ✅ Council no longer falls back to the server's OPENAI_API_KEY env var (was exfiltratable via a caller-chosen endpoint)
- ✅ council_system_prompt no longer read from the filesystem (was arbitrary file read over the API)
- ✅ CORS restricted to local origins (was "*"); GET/POST only
- ✅ Security headers: CSP, X-Frame-Options: DENY, X-Content-Type-Options: nosniff
- ✅ /runs input validation: unknown attack_id / empty goals / >500 goals / blocked target → 400
- ✅ Frontend: "Read the paper" link validates http(s) scheme (was a javascript:-URL key-theft vector)
- ✅ Scrubbed internal cluster IPs (10.0.0.x / "pasarea") from vendored council source
- ✅ SQLite file chmod 600; untracked committed run outputs (results/) + gitignored
- ✅ (already good, verified) secret redaction on REST/WS/disk, git history clean, no eval/exec, SQL parametrized, target output rendered via textContent (no XSS)

### Remaining ⬜
- ⬜ [High] Optional backend auth token (no auth today; fine for local single-operator, needed before shared/public hosting)
- ⬜ [Med] Pydantic request models for all endpoints (replace dict[str,Any])
- ⬜ [Med] DoS caps: max concurrent runs, request body-size limit, bound in-memory backlog, per-call timeout
- ⬜ [Med] Broaden redaction to credential-in-URL and more field names (authorization/password/secret)
- ⬜ [Low] Generic client error messages (avoid echoing endpoints); remove unused React scaffold (frontend/src); coerce numeric UI interpolations; consider self-hosting fonts / SRI

## Backlog (later) ⬜
- ⬜ GraphQL + subscriptions (scale beyond raw WS)
- ⬜ More target connectors (agent endpoints, guarded connectors)
- ⬜ Benchmark / leaderboard; contributor docs; public launch
- ⬜ Name clearance (trademark/domain) before going public
