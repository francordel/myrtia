# Myrtia

Open-source, **agent-native AI/LLM red-teaming framework** with a web front-end.
Licensed under **Apache-2.0** (see [`LICENSE`](LICENSE)).

> **Name (working):** *myrtia* — the round shield of the **rodeleros**, the elite
> sword-and-buckler infantry of the Spanish *Tercios*, whose role was to slip in
> between the enemy pikes and break the formation from the inside. A fitting image
> for a red-teaming tool: agile, gets past the target's defences, probes from within.
> The name may still change; renaming is a cheap search-and-replace, so it does not
> block development.

The goal: what IBM ARES and NVIDIA garak are for LLM red-teaming, but built around
**autonomous agents** and shipped with a real UI and observability — aiming to become
an industry-standard tooling layer for **AI/LLM red teaming**.

**Scope (fixed):** probing models and agents for unsafe behaviour — jailbreaks, prompt
injection, multi-turn contextual priming, harmful-output elicitation, agent misuse.
**Out of scope:** network penetration testing and offensive security ops (no Kali,
nmap/metasploit/sqlmap, no exploit execution). The "target" is an LLM or an agent, not
a network.

> Status: greenfield. This repository is an **independent project**, not a fork.
> PentAGI (MIT) is used as a *study reference only* under
> `../pentagi-reference`; any code adopted from it is tracked in
> [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) and must satisfy the rules there.

## Why

- Existing LLM red-teaming frameworks (ARES, garak) are library/CLI-first and not agent-native.
- Autonomous-agent frameworks (e.g. PentAGI) exist but are network-pentest-oriented and
  carry licensing constraints (an AGPL cloud SDK) that block clean commercial reuse.
- Myrtia targets the gap: **agent orchestration + LLM-attack library + judges/scoring +
  LLM/agent target connectors + observability + web UI**, permissively licensed and
  standardisable. From PentAGI we borrow only the generic scaffolding (orchestration loop,
  web UI with human-in-the-loop, observability wiring) — not its pentest tooling.

## Where Fran's prior work plugs in

- Multi-agent attacker orchestration (CouncilAttack: propose → critique → aggregate → chair).
- Graded harm judging / scoring pipelines and matched-budget evaluation.
- The defensive counterpart (propose–critique–vote guardrail panel) — the attack/defence loop.

## Repo layout (to grow)

```
docs/        design, planning, provenance, reference maps
backend/     Python: orchestrator + ARES-compatible plugins + connectors + judges + API
frontend/    React/Vite UI (live deliberation) + a zero-build standalone.html viewer
```

See [`docs/architecture.md`](docs/architecture.md) for module boundaries, the event
schema, and the CouncilAttack integration plan.

See [`PLANNING.md`](PLANNING.md) for the phased plan and open decisions.
