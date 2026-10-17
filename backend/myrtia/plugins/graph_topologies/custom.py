"""Custom topology: execute an arbitrary agent DAG defined by the canvas `edges`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from myrtia.plugins.graph_topologies.base import Topology, get_topology, register

if TYPE_CHECKING:
    from myrtia.plugins.graph import GraphAttack


@register("custom", "graph", "free")
class CustomTopology(Topology):
    """Run the free-form directed graph from `edges`; fall back to council if absent/cyclic."""

    def run_turn(self, eng: "GraphAttack", goal: str, turn: int, gi: int) -> str:
        if not eng.edges:
            return get_topology("council").run_turn(eng, goal, turn, gi)
        by_id = {a["id"]: a for a in eng.agents}
        adj: dict[str, list[str]] = {n: [] for n in by_id}
        indeg: dict[str, int] = {n: 0 for n in by_id}
        strikers: list[str] = []
        for f, t in eng.edges:
            if f in by_id and t in by_id:
                adj[f].append(t)
                indeg[t] += 1
            elif f in by_id and t == "target":
                strikers.append(f)
        # Kahn topological sort (sorted for determinism); cycle -> fall back.
        queue = sorted(n for n in by_id if indeg[n] == 0)
        order: list[str] = []
        deg = dict(indeg)
        while queue:
            n = queue.pop(0)
            order.append(n)
            for m in adj[n]:
                deg[m] -= 1
                if deg[m] == 0:
                    queue.append(m)
            queue.sort()
        if len(order) != len(by_id):
            eng._emit("log", level="warning", turn=turn, goal_index=gi,
                      message="Custom graph has a cycle; falling back to council.")
            return get_topology("council").run_turn(eng, goal, turn, gi)
        preds: dict[str, list[str]] = {n: [] for n in by_id}
        for f in adj:
            for t in adj[f]:
                preds[t].append(f)
        out: dict[str, str] = {}
        eng._turn_proposals = []
        idx = 0
        for nid in order:
            if eng._is_cancelled():
                break
            a = by_id[nid]
            if not preds[nid]:
                prod = eng._draft(a, goal)
            else:
                listing = "Inputs from upstream agents:\n" + "\n\n".join(
                    f"[{i}] {eng._candidate_text(out[p])}" for i, p in enumerate(preds[nid]) if out.get(p))
                prod = eng._synthesize(a, goal, listing, "Combine and refine into")
            out[nid] = prod or ""
            if out[nid]:
                eng._turn_proposals.append({"original_index": idx, "model": a["model"],
                                            "proposal": eng._candidate_text(out[nid])})
                eng._emit("proposal.created", turn=turn, goal_index=gi, original_index=idx,
                          model=a["model"], mutator=f"{a['id']}·graph",
                          proposal=eng._candidate_text(out[nid]))
                idx += 1
        producers = [s for s in strikers if out.get(s)] or (
            [order[-1]] if order and out.get(order[-1]) else [])
        if len(producers) > 1:
            props = [{"original_index": i, "model": by_id[p]["model"], "proposal": out[p]}
                     for i, p in enumerate(producers)]
            winner = eng._borda_vote(goal, turn, gi, props)
            return winner["proposal"]
        if producers:
            eng._turn_winner = (0, by_id[producers[0]]["model"])
            return out[producers[0]]
        raise ValueError("Custom graph produced no prompt wired to the target")
