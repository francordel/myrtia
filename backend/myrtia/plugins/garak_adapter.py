"""NVIDIA garak adapter — run a real garak probe's corpus as a Myrtia attack.

Installing the `garak` pack adds this attack. The operator picks a garak probe
(e.g. `encoding.InjectBase64`, `dan.DanInTheWildFull`, `latentinjection.LatentInjectionResume`);
Myrtia loads that probe, takes its real prompt corpus, sends each prompt to the target
through Myrtia's own connector, and grades every reply 0-5 with the default evaluator.
Each prompt is its own ASR data point, so garak runs feed the same dashboard and audit
reports as every other Myrtia attack.

This exposes garak's full probe catalogue (far wider than Myrtia's native garak-style
subset in `garak_probes.py`) without reimplementing it. We use garak's prompts and
Myrtia's 0-5 judge rather than garak's keyword detectors, so scoring is consistent
with the rest of the platform. garak is imported lazily inside `attack()`, so this
module and the registry load fine when the pack is not installed; the import only
fires when a `garak` run is launched.

garak is Apache-2.0 (github.com/NVIDIA/garak).
"""

from __future__ import annotations

import io
import contextlib
import os
from typing import Any

from myrtia.judges.graded import JUDGE_SCHEMA, judge_and_emit, judge_from_config
from myrtia.plugins.base import PluginSpec, register
from myrtia.plugins.live_base import LiveAttack

_MOD = "myrtia.plugins.garak_adapter"
_DEFAULT_PROBE = "encoding.InjectBase64"
_DEFAULT_CAP = 20


def _load_probe(probe_id: str):
    """Load a garak probe by its id (with or without the `probes.` prefix).

    garak chatters to stdout on load; we swallow it so it never corrupts the API
    process output."""
    from garak import _config, _plugins

    _config.load_base_config()
    if getattr(_config.transient, "reportfile", None) is None:
        _config.transient.reportfile = open(os.devnull, "w")  # noqa: SIM115
    pid = probe_id.strip()
    if not pid.startswith("probes."):
        pid = "probes." + pid
    with contextlib.redirect_stdout(io.StringIO()):
        return _plugins.load_plugin(pid), pid.split(".", 1)[1]


def _prompt_text(p: Any) -> str:
    """garak prompts are plain strings in current builds; tolerate Conversation too."""
    if isinstance(p, str):
        return p
    last = getattr(p, "last_message", None)
    if callable(last):
        msg = last()
        return getattr(msg, "text", str(msg))
    return str(p)


class GarakProbeAttack(LiveAttack):
    """Drive one garak probe's prompt corpus through the Myrtia target, graded 0-5."""

    def __init__(self, config: dict[str, Any], target_connector: Any) -> None:
        self.config = dict(config)
        self.target_connector = target_connector
        self.probe_id = str(self.config.get("probe") or _DEFAULT_PROBE).strip()
        try:
            self.cap = max(1, int(self.config.get("max_prompts") or _DEFAULT_CAP))
        except (TypeError, ValueError):
            self.cap = _DEFAULT_CAP
        self._judge = judge_from_config(self.config)
        self.attack_goals: list[dict] | None = None
        self.attack_results: list[dict] | None = None

    def load_goals(self, goals: list[str]) -> None:
        # garak probes carry their own fixed corpus, so operator goals are not used to
        # build prompts; the seam is kept so the orchestrator drives this like any plugin.
        self.attack_goals = [{"goal": str(g), "label": 1} for g in (goals or [])]

    def attack(self, **kwargs: Any) -> list[dict]:
        from myrtia.connectors.base import Status

        try:
            probe, short_id = _load_probe(self.probe_id)
        except Exception as e:  # noqa: BLE001 — surface a clean message, never a stack
            self._emit("error", message=f"garak probe {self.probe_id!r} failed to load: "
                                         f"{type(e).__name__}: {e}")
            self.attack_results = []
            return []

        probe_goal = (getattr(probe, "goal", "") or f"garak {short_id}").strip()
        prompts = [_prompt_text(p) for p in (getattr(probe, "prompts", None) or [])]
        prompts = [p for p in prompts if p][: self.cap]
        n = len(prompts)
        rows: list[dict] = []

        for i, prompt in enumerate(prompts):
            if self._is_cancelled():
                break
            # A distinct goal key per prompt so each is its own ASR data point, while the
            # judge still scores against the probe's real goal.
            self._emit("goal.started", goal=f"{probe_goal} [{short_id} {i + 1}/{n}]",
                       variant=short_id)
            resp = self.target_connector.generate(prompt, **kwargs)
            text = resp.response if resp.status == Status.SUCCESS else f"[ERROR] {resp.error_message}"
            self._emit("target.responded", variant=short_id,
                       target_prompt=prompt, target_response=text)
            score = judge_and_emit(self._judge, self._emit, probe_goal, text, variant=short_id)
            row = {"goal": probe_goal, "variant": short_id, "prompt": prompt, "response": text}
            if score is not None:
                row["score"] = score
            rows.append(row)

        self.attack_results = rows
        return rows

    def generate(self, **kwargs: Any) -> list[dict]:
        return self.attack_results or []


def _factory(config: dict[str, Any], target_connector: Any) -> GarakProbeAttack:
    return GarakProbeAttack(config, target_connector)


register(PluginSpec(
    plugin_id="garak",
    factory=_factory,
    description="garak probe (NVIDIA garak): runs a chosen garak probe's real prompt "
    "corpus against the target and grades each reply 0-5 with the default evaluator. "
    "Opens garak's full probe catalogue (encoding, dan, latentinjection, goodside, ...). "
    "Requires the garak pack.",
    paper="https://arxiv.org/abs/2406.11036",
    config_schema=[
        {"key": "probe", "label": "garak probe", "type": "text", "default": _DEFAULT_PROBE,
         "help": "A garak probe id, e.g. encoding.InjectBase64, dan.DanInTheWildFull, "
                 "latentinjection.LatentInjectionResume, goodside.Tag. Run `garak "
                 "--list_probes` for the full catalogue."},
        {"key": "max_prompts", "label": "Max prompts", "type": "number", "default": _DEFAULT_CAP,
         "help": "Cap on how many of the probe's prompts to send (its corpus can be "
                 "hundreds). Each prompt is graded 0-5 and counts towards ASR."},
    ] + JUDGE_SCHEMA,
    how=[
        "Pick — choose a garak probe; Myrtia loads its real prompt corpus.",
        "Send — each prompt goes to the target through Myrtia's connector (capped).",
        "Grade — the evaluator scores every reply 0-5, feeding the ASR dashboard.",
    ],
))
