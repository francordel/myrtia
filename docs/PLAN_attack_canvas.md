# Plan: the attack canvas (graph-defined multi-agent attacks)

Goal: a researcher draws an attack as a graph on a canvas (target, judge, attackers, chairmen, critics, static templates), edits every node (model, endpoint, system prompt), and Myrtia **executes that exact graph**, streams it live on the same canvas, and measures it with the same ASR pipeline. Council becomes one preset among many, not the only shape.

Why this is new work: the current council engine (`ares-council`) has a fixed pipeline (propose → critique → Borda → chairman → target → judge). It cannot run a second chairman, a chain of agents, a debate, or parallel strikes. The canvas therefore needs its own engine. Single-turn attacks fit the same model as a static "transform" node, which unifies both families.

---

## 1. Target architecture

```
frontend/standalone.html            backend/myrtia/
┌──────────────────┐  graph JSON   ┌──────────────────────────┐   events   ┌──────────┐
│ Canvas editor    │ ───────────▶  │ plugins/graph.py         │ ─────────▶ │ WS/UI    │
│ (SVG, popovers)  │               │  GraphAttack (executor)  │            │ stream + │
│ presets, export  │ ◀───────────  │  graph/spec.py (schema)  │            │ live     │
└──────────────────┘   validation  │  graph/nodes/*.py        │            │ canvas   │
                                   │  graph/aggregate.py      │            └──────────┘
                                   └──────────────────────────┘
```

- **One new plugin**, `graph`, registered like the others (`attack_id: "graph"`, `attack_config: {graph: {...}}`). No change to `/runs`, `/stats`, WS or the event bus contract.
- **`ares-council` stays untouched** so the paper's numbers remain reproducible. A "Council (paper)" preset compiles to a graph that must match it; a parity test proves it.
- **Single-turn attacks** are re-expressed as a `transform` node (template with `{goal}`, encoding, splitting) so they live on the same canvas and get the same judge.

## 2. Graph specification (`backend/myrtia/graph/spec.py`)

```jsonc
{
  "version": 1,
  "turns": 3,                       // outer loop; feedback edges only cross turn boundaries
  "stop": {"score_gte": 5},         // stop the