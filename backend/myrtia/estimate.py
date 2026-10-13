"""Run-time estimation (issue #38).

A rough wall-clock estimate for a run, from three things: how many model calls the
attack implies (derived from its config), a per-call latency taken from a hardware
profile (local CPU vs local GPU vs a hosted API vs a saved cluster), and how much of
that runs in parallel. It is a planning aid, not a promise — the real number depends
on model size, prompt length and load — so we return the assumptions alongside it.
"""

from __future__ import annotations

from typing import Any

# Per-call latency (seconds) for a single model round-trip, by where the model runs.
HARDWARE_PROFILES: dict[str, dict[str, Any]] = {
    "local-cpu": {"label": "Local CPU (small model)", "per_call": 9.0, "parallel": 1},
    "local-gpu": {"label": "Local GPU (Ollama / small vLLM)", "per_call": 1.6, "parallel": 2},
    "cluster": {"label": "GPU cluster (vLLM, batched)", "per_call": 0.9, "parallel": 8},
    "cloud-api": {"label": "Hosted API (frontier)", "per_call": 3.0, "parallel": 4},
}
DEFAULT_PROFILE = "local-gpu"

# Attacks whose default is a single strike per goal (one target call, plus the judge).
_SINGLE_TURN = {"direct", "obfuscation", "payload-splitting", "human-jailbreak",
                "garak-probes", "contextual-jailbreak", "latent-injection"}


def _int(cfg: dict, *keys: str, default: int = 0) -> int:
    for k in keys:
        v = cfg.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return int(v)
    return default


def calls_per_goal(attack_id: str, cfg: dict[str, Any]) -> dict[str, int]:
    """Estimate the model calls one goal costs, broken down by role."""
    cfg = cfg or {}
    judge_on = str(cfg.get("judge_model", "")).strip().lower() not in {"off", "none", "no", "-"}
    judge = 1 if judge_on else 0

    if attack_id in _SINGLE_TURN or attack_id == "direct":
        return {"target": 1, "judge": judge}

    if attack_id in {"crescendo", "council-crescendo", "tap"}:
        turns = _int(cfg, "max_turns", "max_rounds", "depth", default=4)
        branch = _int(cfg, "branching_factor", "width", default=1) or 1
        return {"attacker": turns * branch, "target": turns, "judge": turns * judge}

    if attack_id == "council":
        turns = _int(cfg, "max_turns", default=3)
        members = len(cfg.get("council_models") or []) or _int(cfg, "n_attackers", default=3)
        critiques = members if cfg.get("use_borda", True) else 0
        chairman = 1 if cfg.get("use_chairman", True) else 0
        return {"proposal": turns * members, "critique": turns * critiques,
                "chairman": turns * chairman, "target": turns, "judge": turns * judge}

    if attack_id == "graph":
        turns = _int(cfg, "max_turns", default=3)
        agents = cfg.get("agents")
        n_attackers = len([a for a in agents if (a or {}).get("role", "attacker") == "attacker"]) if isinstance(agents, list) and agents else _int(cfg, "n_attackers", default=2)
        n_chairmen = len([a for a in agents if (a or {}).get("role") == "chairman"]) if isinstance(agents, list) and agents else (1 if cfg.get("use_chairman") else 0)
        mode = cfg.get("mode", "council")
        critiques = n_attackers if (mode == "council" and cfg.get("use_borda", True)) else 0
        rounds = _int(cfg, "debate_rounds", default=2) if mode == "debate" else 1
        return {"proposal": turns * n_attackers * rounds, "critique": turns * critiques,
                "chairman": turns * max(1, n_chairmen), "target": turns, "judge": turns * judge}

    # Unknown attack: assume one strike + judge.
    return {"target": 1, "judge": judge}


def estimate_run(attack_id: str, attack_config: dict[str, Any], n_goals: int,
                 profile: str = DEFAULT_PROFILE) -> dict[str, Any]:
    prof = HARDWARE_PROFILES.get(profile) or HARDWARE_PROFILES[DEFAULT_PROFILE]
    n_goals = max(0, int(n_goals or 0))
    per_goal = calls_per_goal(attack_id, attack_config or {})
    calls_1 = sum(per_goal.values())
    total_calls = calls_1 * n_goals
    per_call = float(prof["per_call"])
    parallel = max(1, int(prof.get("parallel", 1)))
    # Goals run sequentially in the MVP; within a goal, independent calls (proposals,
    # critiques) can overlap up to the profile's parallelism.
    seconds = round(total_calls * per_call / parallel)
    return {
        "profile": profile, "profile_label": prof["label"],
        "n_goals": n_goals, "calls_per_goal": calls_1, "total_calls": total_calls,
        "per_call_seconds": per_call, "parallelism": parallel,
        "estimated_seconds": seconds,
        "breakdown": {k: v for k, v in per_goal.items() if v},
        "note": "Rough estimate; real time depends on model size, prompt length and load.",
    }
