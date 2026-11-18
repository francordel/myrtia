# Tasks 011 — Agent Skills Attacks

> Small tasks (about 20–30 minutes each) in dependency order. Implement one at a time,
> test first: write the failing scenario or unit test, make it pass with the minimum
> code, refactor, run the checks, tick the box, stop.

- [x] **T1 — Write the acceptance scenarios** (FR-1, FR-2, FR-3, FR-4, FR-5)
  Add `backend/tests/features/skills_attacks.feature` from `spec.md`, with step definitions in `backend/tests/test_skills_attacks_bdd.py`.
  Done when: the offline scenarios are collected by `pytest` and fail because the `"skills-attacks"` plugin does not exist yet.

- [x] **T2 — Implement canonical skill attack scenarios and simulated tool sandbox** (FR-2, FR-3, NFR-1)
  Write failing unit tests in `backend/tests/test_skills_attacks.py` for the 5 canonical literature families (`direct_override`, `contextual_exfil`, `yaml_metadata_poison`, `resource_indirect_inject`, `cross_skill_hijack`), canary-only payloads, and deterministic simulated tools (`read_file`, `write_file`, `read_resource`, `send_http`, `run_shell`), then implement the scenario & sandbox layer in `backend/myrtia/plugins/skills_attacks.py`.
  Done when: all scenario and sandbox unit tests pass.

- [x] **T3 — Implement `SkillsAttackLive` loop, forbidden-action detection, and plugin registration** (FR-1, FR-4, FR-5, FR-6, FR-7)
  Write failing unit tests in `backend/tests/test_skills_attacks.py` for variant filtering, `max_turns` budget, malformed tool-call JSON, forbidden-action flagging, structured event emission, and connector error handling; then implement `SkillsAttackLive` and `register(PluginSpec(plugin_id="skills-attacks", ...))` in `backend/myrtia/plugins/skills_attacks.py`.
  Done when: `uv run --extra dev ruff check backend` and `uv run --extra dev pytest -m "not e2e"` pass with zero warnings.

- [x] **T4 — Validate the spec** (FR-1 … FR-7, NFR-1, NFR-2)
  Walk `spec.md` requirement by requirement, state what test proves each one, and confirm `Definition of done`.
  Done when: every requirement is covered, all checks are green, and the verdict is reported.

- [x] **T5 — Render `skill.*` events cleanly in the live UI** (FR-8)
  Add a UI scenario in `backend/tests_ui/features/agent_attacks.feature` (and `test_agent_attacks_ui.py`), see it fail, then update `evNode` in `frontend/standalone.html` to format `skill.*` events with human-readable labels and warning styling for `skill.forbidden_action`.
  Done when: `ruff check backend`, `pytest -m "not e2e"`, and `pytest backend/tests_ui` pass.

