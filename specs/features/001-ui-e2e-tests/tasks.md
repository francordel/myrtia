# Tasks 001 — Automated behaviour scenarios for the web UI

> Small tasks (about 20–30 minutes each) in dependency order. Implement one at a time,
> test first: write the failing scenario or unit test, make it pass with the minimum
> code, refactor, run the checks, tick the box, stop.
>
> Notes from implementation: T4 was done before T3, because the full run is launched
> through the private instance. T9 needed no `data-testid`: existing selectors sufficed.
> In T8–T10 each behaviour was broken once in the page and its scenario failed; the
> page was restored and is unchanged by this feature.
> T11 measured: one run takes 31–46 s; twenty consecutive runs, twenty passes.
> T12 is written but only proven by the first pull-request run, and T14's two
> pull-request checks (FR-14, FR-15) wait for it too; every other requirement is
> validated.

- [x] **T1 — Add the UI tier skeleton and dependencies** (FR-1, FR-5, NFR-5)
  Create `backend/tests_ui/` with an empty `conftest.py`. Add the `ui` extra
  (`pytest-playwright`) to `backend/pyproject.toml` and the `ui` group to the root
  `pyproject.toml`. Add `test-results/` to `.gitignore`.
  Done when: `uv run --group ui pytest backend/tests_ui` collects zero tests without
  error, and `uv run --extra dev pytest -m "not e2e"` still reports 110 passed.

- [x] **T2 — Simulated model server** (FR-7, FR-9)
  Write unit tests first for `fake_model.py`: `GET /api/tags`, `GET /v1/models`,
  `POST /v1/chat/completions` (fixed content and `usage`), unknown path gives 404, and
  the judge's `parse_score` returns `(1, "Simulated verdict.")` for the fixed reply.
  Then implement the server with the standard library, started on a free port.
  Done when: those unit tests pass.

- [x] **T3 — Prove a full run works against the simulated model, without a browser**
  (FR-7)
  Write a test that starts the simulated model, launches the default graph attack
  through the API with one goal and all agents on `sim-model`, and waits for the run to
  finish. Add request-specific replies to the server only if a role rejects the fixed
  text.
  Done when: the run ends with status finished, with a target response and a judge
  score of 1; any extra reply rule is covered by a unit test.

- [x] **T4 — Application launcher** (FR-2, FR-3, FR-13)
  Unit tests first: picks a free port, sets `MYRTIA_DB`, `MYRTIA_GOAL_DATA_DIR` and
  `MYRTIA_OLLAMA_URL`, drops `MYRTIA_TOKEN`, waits until the app answers, raises an
  error containing the startup output when it never becomes ready, and on exit leaves
  no process and no temporary file. Then implement it as a session fixture.
  Done when: those unit tests pass.

- [x] **T5 — Browser context fixture** (FR-6, FR-8, FR-12)
  Tests first: requests to any host other than `127.0.0.1` are aborted; a missing
  browser executable produces the message with the install command; `--headed` is
  honoured. Then implement the per-scenario context (1280×800, empty storage).
  Done when: those tests pass and a trivial test can open the application's page.

- [x] **T6 — Failure evidence and script-error guard** (FR-10, FR-11)
  Write `features/harness.feature` scenarios "A failing scenario leaves evidence" and
  "A script error fails the scenario" with their steps (an inner pytest run for the
  first). Then implement the teardown that saves `screenshot.png` and `console.txt`
  and fails on unhandled page errors.
  Done when: both scenarios pass.

- [x] **T7 — Isolation scenarios** (FR-4, FR-8)
  Add to `harness.feature`: "The operator's data is untouched" (sentinel database at
  the default path, byte-identical afterwards) and "Nothing leaves the machine".
  Done when: both scenarios pass.

- [x] **T8 — Baseline scenarios 1–3: open, add, remove** (FR-16.1 – FR-16.3)
  Write `features/builder.feature` with the first three scenarios and see them fail
  for missing steps. Implement the steps using existing ids and `.gnode[data-id]`.
  Break each behaviour once in a scratch edit to confirm the scenario fails, then
  revert.
  Done when: the three scenarios pass and each was seen failing against the broken
  behaviour.

- [x] **T9 — Baseline scenarios 4–5: edit model, change topology** (FR-16.4, FR-16.5,
  NFR-4)
  Same procedure. Add `data-testid` attributes to `standalone.html` only where no
  stable selector exists, and list them in the pull request.
  Done when: both scenarios pass, each was seen failing against the broken behaviour,
  and the page looks and behaves the same.

- [x] **T10 — Baseline scenario 6: a run shown live** (FR-16.6)
  Same procedure, with every agent on the simulated model and the goal "Say hello".
  Wait on visible state only, never on fixed delays.
  Done when: the scenario passes and was seen failing against a broken behaviour.

- [x] **T11 — Speed and stability** (NFR-1, NFR-2, NFR-3)
  Measure the wall time of the tier and run it twenty times in a row.
  Done when: one run takes under two minutes and twenty consecutive runs pass; the
  numbers are recorded in the pull request.

- [ ] **T12 — Continuous integration job** (FR-14, FR-15)
  Add the `ui-scenarios` job to `.github/workflows/ci.yml`: install `.[dev,ui]`,
  install Chromium with a cache keyed on the Playwright version, run the tier, and
  upload `backend/test-results/` when it fails.
  Done when: the job is green on the feature's pull request.

- [x] **T13 — Documentation and constitution wording** (FR-5, FR-12)
  Document install and run commands in `CONTRIBUTING.md`; mention the UI tier and its
  folder in `AGENTS.md` and `specs/README.md`; update principle 9 in `tech-stack.md`
  to name the UI tier instead of a manual browser check.
  Done when: a reader can install and run the tier from the documentation alone.

- [ ] **T14 — Validate the spec** (all)
  Walk `spec.md` requirement by requirement and state what proves each one. Perform the
  manual checks: a pull request that breaks a baseline behaviour shows a red check with
  downloadable evidence (FR-14, FR-15); `--headed` opens a window (FR-6); the offline
  command passes in an environment without Playwright (FR-5).
  Done when: every requirement is covered and the verdict is written in the pull
  request. Mark the feature as Done in `roadmap.md`.
