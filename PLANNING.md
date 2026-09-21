# Myrtia — planning

Working method: small, verifiable loops ("loop engineering"). Each phase ends in
something runnable or a written decision, not a big-bang. Provenance and licence are
checked continuously (see `THIRD_PARTY_NOTICES.md`), not at the end.

## Open decisions (resolve in Phase 0, they shape everything)

- **D1 — Licence of Myrtia. RESOLVED = Apache-2.0** (see the D1 entry below / `LICENSE`).
- **D2 — Reuse vs rewrite the stack.** PentAGI is Go backend + React frontend. Reuse the
  MIT-clean parts (orchestration loop, docker sandbox, observability wiring, UI shell) or
  rewrite for a cleaner base and full ownership? Likely hybrid: reuse patterns, rewrite core.
- **D3 — RESOLVED. Scope = AI/LLM red teaming only.** Probing models and agents for
  unsafe behaviour (jailbreaks, prompt injection, multi-turn priming, harmful elicitation,
  agent misuse). NOT network pentest / offensive security ops. The target is an LLM or an
  agent, never a network. This is the ARES/garak/CouncilAttack space.
- **D4 — Name. RESOLVED (working name = "Myrtia").** The rodeleros' round shield
  (Spanish *Tercios*): a red-teamer that slips past defences and breaks the formation
  from inside. "AgentShield" and "Adarga" were dropped (both taken by funded AI
  security/defence companies); "AgentKeeper" collides with an AI-agent-security product
  (RAD Security). Myrtia shows no direct AI/security collision in a first pass. Full
  clearance (USPTO/EUIPO, GitHub/PyPI/npm, domains) still pending before anything
  public; name may still change (cheap rename), so it does not block Phases 2-3.
- **D1 — RESOLVED. Licence = Apache-2.0** (`LICENSE` in repo root). Permissive + patent
  grant, best for an industry-standard tooling layer. Source-available (BSL) was
  considered and set aside.

## Phases

### Phase 0 — Foundations
Resolve D1–D4. Pick backend/frontend languages. Set up repo hygiene: licence file, CI,
lint, pre-commit, the provenance log. Define the one-line product thesis.

### Phase 1 — Understand the reference (analysis, no copying)
We only care about PentAGI's **generic scaffolding**, since its pentest tooling is out of
scope: (a) the agent orchestration loop, (b) the React web UI with human-in-the-loop
approve/deny, (c) the observability wiring (Grafana, Langfuse, VictoriaMetrics, Jaeger,
Loki, OTel), (d) provider/LLM integration. The docker sandbox + security-tool executor +
Kali images are **ignored** (network-pentest specific). **License audit** limited to the
modules we might reuse: which are MIT-clean vs which touch `github.com/vxcontrol/cloud`.
Deliverable: `docs/reference-map.md` + a keep/avoid table.

### Phase 2 — Myrtia architecture
Define our module boundaries: (a) agent orchestration, (b) **LLM attack/technique
library** (jailbreak, prompt injection, multi-turn contextual priming, encoding, etc.),
(c) **target connectors for LLMs/agents** (chat APIs, self-hosted, agentic endpoints),
(d) judges & scoring (graded harm, matched-budget eval — Fran's CouncilAttack judging),
(e) observability, (f) web UI with human-in-the-loop. A plugin API so the community can
add attacks/targets/judges.
Deliverable: `docs/architecture.md` + interfaces.

### Phase 3 — MVP (end-to-end thin slice)
**Definition of done (MVP):** CouncilAttack runs end-to-end inside Myrtia, driven
from the web UI. The operator launches it against a target LLM; the full deliberation
loop executes (propose -> cross-critique -> Borda Top-1 -> chairman synthesis -> in-loop
graded judge); and the UI + observability show each council member / chairman / judge and
each turn activating live, ending with the harm scores. No breadth yet (one attack, one
target, one judge) -- the point is to prove the whole loop works through Myrtia.

CouncilAttack already exists as an ARES plugin (`ares-council`), so the MVP is mostly an
*integration*: Myrtia's shell (orchestration + LLM/target connectors + observability
+ UI) has to host and drive that attack. This sets two hard requirements for Phase 2:
(i) an attack/plugin interface that can run CouncilAttack (adapt the ares-council plugin,
do not vendor anything AGPL), and (ii) a UI that renders a multi-agent deliberation live,
which is exactly the "see the agents activate" view.

### Phase 4 — Build out
Attack modules, more connectors, dashboards, sandbox hardening, tests, docs. Iterate in
loops; each attack/connector is a self-contained PR with tests.

### Phase 5 — Toward a standard
Stable plugin API, a benchmark/leaderboard, positioning vs ARES/garak, contributor docs,
public launch. The defensive counterpart (guardrail panel) as a differentiator.

## Cross-cutting rules
- Nothing importing `github.com/vxcontrol/cloud` enters the repo.
- Every adopted snippet logged in `THIRD_PARTY_NOTICES.md` with origin + licence.
- No PentAGI branding anywhere.
- Small PRs, each runnable/tested. Security tooling → authorised-use notice from day one.

## How we execute
Bounded agent tasks for the analysis-heavy parts (Phase 1 reference map + licence audit,
Phase 2 interface drafts), reviewed before merge. Building the product itself stays
human-driven in small loops, not auto-generated wholesale.
