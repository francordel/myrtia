<div align="center">

# MYRTIA

**Agent-native red teaming for LLMs and AI agents.**

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-1a73e8.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-alpha-orange.svg)](BACKLOG.md)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776ab.svg)](backend/pyproject.toml)

</div>

---

Myrtia is an open-source framework for **red teaming large language models and AI agents**:
it drives a *council of attacker models* that deliberate, cross-critique and vote to craft
adversarial prompts, sends them to a target model, and grades the outcome with an in-loop
judge — all streamed live through a web UI.

Where library/CLI tools such as IBM **ARES** and NVIDIA **garak** are the reference point
for LLM red teaming, Myrtia is built around **autonomous multi-agent attackers** and ships
with a real front-end and analytics, so you can *watch* an attack unfold turn by turn and
measure Attack Success Rate across behaviours, themes, targets and attacks.

> The name **Myrtia** (Latin *Myrtea*, "place of myrtles"; the Roman goddess **Murcia**)
> is the ancient root of the name of the city of Murcia. A tool from the *huerta*, aimed at
> the frontier.

Myrtia red teaming revolves around four components:

* **Attacks** — how adversarial prompts are generated (a deliberating council, crescendo, or direct).
* **Targets** — the model or agent under test (any OpenAI-compatible endpoint: OpenAI, Anthropic, self-hosted vLLM, Ollama).
* **Judge & scoring** — a graded 0–5 harm judge, aggregated into Attack Success Rate (ASR).
* **Behaviours** — what you attack (a built-in HarmBench library, selectable by theme, or your own goals).

## ✨ Key Features

- **CouncilAttack, live.** N proposer models propose → cross-critique → Borda Top-1 vote →
  chairman synthesis → in-loop graded judge, rendered **live over WebSocket**, turn by turn.
- **Multiple attacks, selectable.** `council`, `council-crescendo` (accumulating multi-turn
  escalation) and `direct` (baseline), each with its own advanced-config schema.
- **Behaviour library.** 278 HarmBench behaviours across 5 themes, with per-theme checkboxes,
  search and select-all — or paste your own goals.
- **Any provider.** OpenAI, Anthropic (OpenAI-compatible endpoint), self-hosted vLLM and local
  Ollama, mixed freely (e.g. an open-model council attacking a frontier target).
- **Analytics dashboard.** ASR by attack / target / theme, judge-score distribution, and — for
  council attacks — per-member vote win-rates.
- **Run history + search.** Every run is searchable/filterable by goal, theme, result and evaluation.
- **Extensible.** Attacks, targets and judges are plugins; the attack contract is
  [ARES](https://github.com/IBM/ares)-compatible.
- **Apache-2.0.** Permissive, self-hostable, no vendor lock-in.

## 🚀 Quickstart

```bash
# 1. backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e .
pip install -e vendor/ares-council        # the CouncilAttack plugin (Apache-2.0)

# 2. run the server (serves the API and the web UI)
uvicorn myrtia.api.app:app --port 8000

# 3. open the UI
open http://127.0.0.1:8000/
```

Pick an **attack**, choose a **target** (OpenAI-compatible base URL + model), select
**behaviours** from the library (or type a goal), and hit **Launch**. The deliberation
streams in live; the run lands in **History** and feeds the **Statistics** dashboard.

To attack a frontier target with a permissive local council (the recommended setup):

| Role | Example |
| --- | --- |
| Council (attackers) | `llama3.2:3b`, `qwen2.5:3b`, `gemma2:2b` on local Ollama |
| Chairman / Judge | a capable model (e.g. Claude via its OpenAI-compatible endpoint) |
| Target | the frontier model under test |

## 🎯 Attacks

| Attack | What it does |
| --- | --- |
| `council` | N-proposer council, cross-critique, Borda Top-1 vote, chairman synthesis, in-loop graded 0–5 judge. Each turn is a fresh standalone prompt. |
| `council-crescendo` | Same council pipeline, but the target conversation **accumulates** across turns — gradual multi-turn escalation. |
| `direct` | Baseline: send each behaviour straight to the target (no judge). |

## 🧠 How it works

For each behaviour, each turn:

1. **Propose** — every council member independently drafts an attack prompt.
2. **Critique & vote** — members rank each other's proposals; **Borda** aggregation picks a winner.
3. **Synthesize** — a chairman refines the winning proposal into the prompt actually sent.
4. **Attack** — the prompt goes to the target model.
5. **Judge** — an in-loop judge grades the target's response 0–5; ≥5 counts as a full jailbreak.

The UI shows each of these steps as it happens; results roll up into ASR.

## 🏗️ Architecture

```
backend/   Python · FastAPI + WebSocket
  myrtia/orchestrator   drives a run, streams events
  myrtia/plugins        attacks (ARES-compatible); council/direct
  myrtia/connectors     OpenAI-compatible target connectors
  myrtia/events         typed event schema + bus (the live-view contract)
  myrtia/data           HarmBench behaviour library
  myrtia/api            REST control + /runs/{id}/events WebSocket
frontend/  web UI (live deliberation, history, behaviour library, dashboard)
```

See [`docs/architecture.md`](docs/architecture.md) for the full design.

## 🔌 Extending

Attacks are [ARES](https://github.com/IBM/ares)-style strategies (a class taking
`(config, target_connector)` with `attack()`), registered as Myrtia plugins with an optional
`on_event` seam for live streaming and a `config_schema` for the UI. Targets are ARES
connectors built from a small spec. Drop a module in `backend/myrtia/plugins/` and register it.

## 🗺️ Roadmap

Tracked in [`BACKLOG.md`](BACKLOG.md) (sprints, known issues, proposals).

## 🙏 Built on

Myrtia stands on the [ARES](https://github.com/IBM/ares) red-teaming abstractions
(connectors, attack strategies) and vendors the CouncilAttack plugin. It is inspired by the
LLM red-teaming work of ARES (IBM) and [garak](https://github.com/NVIDIA/garak) (NVIDIA).

## 📄 License

[Apache-2.0](LICENSE).

## ⚠️ Responsible use

Myrtia is for **authorised** AI safety and security testing — evaluating models and agents you
own or have permission to test. Do not use it to produce or distribute harmful content or to
attack systems without authorisation.
