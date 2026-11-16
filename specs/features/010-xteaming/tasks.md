# Tasks 010 — X-Teaming multi-agent attack

> Small tasks in dependency order. Implement one at a time, test first: write the failing
> scenario or unit test, make it pass with the minimum code, refactor, run the checks,
> tick the box, stop.

- [x] **T1 — Write the acceptance scenarios** (FR-1 … FR-15)
  Add `backend/tests/features/xteaming.feature` and `backend/tests/test_xteaming.py` with
  stub planner/attacker/verifier/target connectors (no network).
  Done when: the scenarios are collected and fail because the plugin does not exist.

- [x] **T2 — Prompts module** (FR-13, FR-14)
  `xteaming_prompts.py`: benign structural defaults for the four roles and the
  `MYRTIA_XTEAMING_PROMPTS_FILE` loader; `.gitignore` entry.
  Done when: the default-content and private-override scenarios pass.

- [x] **T3 — Planner and plan loop** (FR-4, FR-8)
  Plan generation, fallback to a single-phase plan, the per-plan loop.
  Done when: a plan is produced and executed.

- [x] **T4 — Attacker, target and verifier** (FR-5, FR-6, NFR-3)
  The per-turn message, the target call within the accumulating conversation, the 1–5
  verifier, phase advance, the success/stop logic.
  Done when: the run-to-success scenario passes.

- [x] **T5 — Prompt optimizer** (FR-7)
  The textual-feedback retry loop on a stalled turn, bounded by the budget.
  Done when: the optimization scenario passes.

- [x] **T6 — Events and cancellation** (FR-9, FR-10, FR-12)
  Emit the plan, turns, messages, replies and scores; stop between turns and plans when
  cancelled.
  Done when: the live-view and cancellation scenarios pass.

- [x] **T7 — Register and configure** (FR-1, FR-2, FR-11)
  `register(PluginSpec(...))` with the description, paper, how-steps and config schema.
  Done when: the registration and configuration scenarios pass.

- [x] **T8 — Provenance and disclosure** (FR-15)
  `THIRD_PARTY_NOTICES.md` row, `DUAL_USE.md` section, roadmap and README lines.
  Done when: the provenance scenario passes.

- [x] **T9 — Validate the spec**
  Walk `spec.md` requirement by requirement, run the checks, confirm the plugin appears in
  `/plugins` and completes against a stub target.
  Done when: every requirement is covered and the verdict is written in the pull request.
