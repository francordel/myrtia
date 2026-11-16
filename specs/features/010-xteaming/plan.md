# Plan 010 — X-Teaming multi-agent attack

> How the spec will be built. Read `specs/constitution/` and this feature's `spec.md`
> first. Every part names the requirements it covers.

## Approach

One plugin, `myrtia.plugins.xteaming`, built on the same seams as Crescendo and TAP:
`LiveAttack` for events and cancellation, `build_target_connector` for the auxiliary
models, and the shared JSON/score parsers. It reimplements the paper's four roles as four
prompted calls to OpenAI-compatible endpoints: the Planner drafts plans, the Attacker
turns a plan into messages, the Verifier scores replies 1–5 (reusing Myrtia's judge
style), and the Optimizer rewrites a stalled message from textual feedback (the paper's
TextGrad, reimplemented as a feedback loop, no dependency). The role prompts live in a
separate module with benign structural defaults in git and a private-file loader, exactly
as `council_official.py` / `MYRTIA_COUNCIL_PHASE2_FILE` do. Nothing is read from the
authors' unlicensed repository.

## Affected areas

| Area | Change | Covers |
|---|---|---|
| `backend/myrtia/plugins/xteaming.py` (new) | The engine: plan loop, four roles, events, config schema, `register` | FR-1 … FR-12 |
| `backend/myrtia/plugins/xteaming_prompts.py` (new) | Benign structural default prompts and the private-file loader | FR-13, FR-14 |
| `backend/tests/features/xteaming.feature`, `backend/tests/test_xteaming.py` (new) | Scenarios and stub-connector steps | all |
| `.gitignore` | Ignore `*.private.yaml` already; add the X-Teaming prompt file name | FR-14 |
| `DUAL_USE.md` | A section on X-Teaming's benign defaults and private operative prompts | FR-13, FR-14 |
| `THIRD_PARTY_NOTICES.md` | Provenance row: reimplemented from the paper, repo unlicensed, not used | FR-15 |
| `specs/constitution/roadmap.md`, `README.md` | Roadmap row; one line in the attack list | FR-1 |

## Data and state

Per goal, the engine holds the list of plans and, per executed plan, the accumulating
target conversation and the best score. A plan is:

```json
{
  "persona": "the role the attacker adopts",
  "context": "the scenario that frames the request",
  "approach": "the named strategy (roleplay | scenario | expand | ...)",
  "phases": ["phase 1 objective", "phase 2 objective", "..."]
}
```

Nothing is persisted beyond the run's results (`response`, `score`, `success`,
`plan`, `turns_used`), which flow through the existing run store.

## Contracts

New plugin id `xteaming`. Config (merged into `attack_config`):

| Key | Default | Meaning |
|---|---|---|
| `n_plans` | 4 | Plans the planner drafts per goal |
| `n_execute` | 2 | Plans actually executed per goal |
| `max_turns` | 7 | Turns per plan before giving up |
| `success_score` | 5 | Verifier score (1–5) that counts as a jailbreak |
| `opt_budget` | 2 | Optimizer retries on a stalled turn |
| `planner_model`, `attacker_model`, `judge_model` | `qwen2.5:3b` | The three auxiliary models |
| `aux_endpoint`, `judge_endpoint` | local Ollama | Their endpoints |

Events (all existing types, so the live view and the trace work unchanged):
`goal.started`, `turn.started` (`{turn: plan index, max_turns}`), `agent.message`
(`{round, model, sender: "planner", message}`), `proposal.created`
(`{turn, model, mutator: approach, proposal}`), `target.responded`, `judge.scored`,
`goal.finished`.

Prompts: `xteaming_prompts.load()` → `{planner, attacker, verifier, optimizer}`. It reads
`MYRTIA_XTEAMING_PROMPTS_FILE` (a YAML with those four keys) when set and valid, else
returns the benign structural defaults shipped in the module.

## UI behaviour

No bespoke UI: `xteaming` appears in the attack list through the plugin registry and
reuses the existing live-view event rendering, dashboards, audit export and traces.

## Decisions

| Decision | Why | Alternative rejected |
|---|---|---|
| Reimplement from the paper, not the repo | The authors' repository carries no licence (all rights reserved); the paper is CC BY 4.0 | Cloning or vendoring the repo: unlicensed, would poison Myrtia's clean-licence position |
| Benign structural defaults + private operative prompts | The repo's established dual-use pattern (council Phase 2, `contextual_jailbreak` scaffolds) | Shipping operative jailbreak prompts: puts worked offensive content in git |
| TextGrad reimplemented as a feedback loop | Keeps X-Teaming dependency-free (NFR-1); the paper's optimizer is a textual gradient | Adding the `textgrad` package |
| Verifier reuses the 1–5 judge style | Consistent scoring with the rest of the platform; feeds the same dashboards | A bespoke scorer |
| One plugin module, built on `LiveAttack` | Matches Crescendo/TAP; events, cancellation and traces work for free | A new engine outside the plugin contract |

## Constitution check

- **4, 5 (extension, boundaries):** a new self-registering plugin; no core edit; imports
  nothing from the API layer.
- **6 (secrets):** keys and auth headers never enter events (same helpers as Crescendo).
- **7 (outbound):** auxiliary endpoints go through `build_target_connector`, which is
  SSRF-guarded.
- **8 (no private dual-use artefacts in git):** operative prompts load from a git-ignored
  private file; only benign structural defaults are committed.
- **11 (test-driven):** scenarios first, seen failing, with stub connectors.
- **12 (traceable):** reuses the existing event types, so metrics and traces cover it.

## Test strategy

| Requirement | Proof |
|---|---|
| FR-1 | "X-Teaming is registered and described" (hits `/plugins`) |
| FR-3, FR-4, FR-5, FR-6, FR-8 | "X-Teaming runs a plan to success" |
| FR-7 | "A stalled turn is optimized before moving on" |
| FR-9, FR-10 | "The live view sees the plan, turns, replies and scores" |
| FR-11 | "The advanced configuration lists every knob" |
| FR-12 | "A cancelled run stops and returns what it has" |
| FR-13 | "The committed defaults carry no worked harmful content" (defaults load; a flagged-phrase check) |
| FR-14 | "A private prompt file overrides the defaults", "A missing file falls back to the defaults" |
| FR-15 | "The provenance is recorded" (THIRD_PARTY_NOTICES names the paper and the unlicensed repo) |
| NFR-3 | "An unreachable verifier does not read as success" |

## Risks

- **Weak default attack:** with the benign defaults the attack is a weak baseline. That is
  intended (FR-13); the field help and DUAL_USE.md point to the private prompt file.
- **Paper reproducibility:** this is a from-paper reimplementation, not the authors' code;
  reported numbers may differ. Stated in the provenance and the plugin description.
- **Convention drift in the plan JSON:** a weak planner model may return malformed plans;
  the engine falls back to a single-phase plan built from the goal.
