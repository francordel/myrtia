# Plan 001 — Automated behaviour scenarios for the web UI

> How the spec will be built. Read `specs/constitution/` and this feature's `spec.md`
> first. Every part names the requirements it covers.

## Approach

Add a third test tier, next to the offline and the live-model tiers: UI scenarios written
in Gherkin, bound with `pytest-bdd` and driven through a real Chromium browser with
Playwright. A session fixture starts two local processes for the tier: a simulated model
server with fixed replies, and a private instance of the Myrtia application pointed at
that server and at a temporary database. Each scenario gets a fresh browser context, so
nothing is shared with the operator's own browser or data. A separate CI job runs the
tier on every pull request.

No application code changes behaviour. The only edits outside the test tree are
identifier attributes in the UI markup, where no stable selector exists.

## Affected areas

| Area | Change | Covers |
|---|---|---|
| `backend/tests_ui/` (new) | The UI tier: fixtures, step definitions, feature files, simulated model | FR-1 … FR-13, FR-16 |
| `backend/tests_ui/features/builder.feature` | The six baseline scenarios | FR-16 |
| `backend/tests_ui/features/harness.feature` | Scenarios about the test system itself | FR-4, FR-8, FR-10, FR-11 |
| `backend/tests_ui/fake_model.py` | Simulated model server (standard library only) | FR-7, FR-9 |
| `backend/tests_ui/conftest.py` | Process lifecycle, browser context, request blocking, error capture | FR-2, FR-3, FR-6, FR-8, FR-10 … FR-13 |
| `backend/pyproject.toml` | New optional extra `ui` (`pytest-playwright`); `ui` marker | FR-5, NFR-5 |
| `pyproject.toml` (root) | New dependency group `ui` so `uv run --group ui …` works | FR-5 |
| `frontend/standalone.html` | `data-testid` attributes only where needed | FR-16 |
| `.gitignore` | Ignore `test-results/` (failure evidence) | FR-10 |
| `.github/workflows/ci.yml` | New job `ui-scenarios` with artefact upload on failure | FR-14, FR-15 |
| `CONTRIBUTING.md`, `AGENTS.md`, `specs/README.md` | How to install and run the tier; where UI scenarios live | FR-5, FR-12 |

## Data and state

- **Application instance.** Started as a subprocess (`uvicorn myrtia.api.app:app`) on a
  port obtained by binding to port 0. Its environment sets:

  | Variable | Value | Why |
  |---|---|---|
  | `MYRTIA_DB` | a file under pytest's temporary directory | empty, private run store (FR-2, FR-4) |
  | `MYRTIA_GOAL_DATA_DIR` | a temporary directory | uploads never reach the real data folder (FR-4) |
  | `MYRTIA_OLLAMA_URL` | the simulated model's address | the UI's default endpoints become the simulated model (FR-7) |

  `MYRTIA_TOKEN` is removed from the environment so the instance is not gated.
- **Browser state.** One new browser context per scenario: empty `localStorage`, so
  stored keys, theme and tokens from the operator's browser are never read (FR-4).
- **Failure evidence.** Written under `backend/test-results/` (added to `.gitignore`): one folder
  per failed scenario with `screenshot.png` and `console.txt` (FR-10).

## Contracts

Simulated model server, on `127.0.0.1:<free port>`:

| Request | Reply |
|---|---|
| `GET /api/tags` | `{"models": [{"name": "sim-model"}]}` |
| `GET /v1/models` | `{"data": [{"id": "sim-model"}]}` |
| `POST /v1/chat/completions` | An OpenAI-style completion whose content is the fixed reply below, with a fixed `usage` block |
| anything else | `404` with an empty JSON object |

Fixed reply for every completion (FR-9), valid for a target, an attacker and the judge
parser at once:

```text
Simulated reply. {"harm": 1, "argument": "Simulated verdict."}
```

The judge parser extracts `harm` and `argument` from that text; every other role treats
it as plain text. If a role in the default topology needs a stricter format (for
example critique rankings), the server gains a rule keyed on a marker in the request,
decided in task T3 from a real run against it.

## UI behaviour

Selectors, in order of preference: existing element ids (`#gAddAtk`, `#gLaunch`,
`#gGoal`), existing data attributes (`.gnode[data-id]` and its role class), then a new
`data-testid`. New `data-testid` attributes are added only for elements with none of
these, and change nothing visible.

## Decisions

| Decision | Why | Alternative rejected |
|---|---|---|
| Playwright through `pytest-playwright` | Same runner and language as the rest of the suite; works with `pytest-bdd` step functions; built-in waiting, headed mode and request routing | Selenium: more setup and manual waits. Cypress or Playwright for Node: a second toolchain, against the Python-only stack |
| Chromium only, 1280×800 | One engine and size keeps the tier fast and stable (NFR-3) | Three engines: triples run time for behaviour that is not engine-specific |
| UI tier in `backend/tests_ui/`, outside `testpaths` | `pytest -m "not e2e"` keeps collecting only `tests/`, so it needs no browser and no new dependency (FR-5) | A `ui` marker inside `tests/`: the existing command would start collecting browser tests |
| Separate extra `ui`, not part of `dev` | The fast tier and CI job stay light; browsers are a large download (NFR-5) | Adding to `dev`: every contributor would need browsers for backend work |
| Simulated model as a standard-library HTTP server in a thread | No new dependency; fully deterministic; exercised through the real connector code | Mocking the connector in-process: the application runs in another process and the real HTTP path would not be tested |
| Real application subprocess | Tests the app as shipped, including static file serving, security headers and the WebSocket | Starlette `TestClient`: a browser cannot connect to it |
| Block external hosts with a browser-context route | Makes FR-8 enforceable and the tier independent of the network; web fonts simply do not load | Allowing the font CDN: scenarios would depend on the internet |
| Fail, do not skip, when the browser is missing | A skipped UI tier would pass silently in CI (FR-12) | Skipping, as the live-model tier does: acceptable there, wrong for a blocking check |
| Script errors fail the scenario in fixture teardown | Catches regressions no assertion looks for (FR-11) | Checking only inside steps: errors after the last step are missed |

## Constitution check

- **Zero-build frontend (2):** nothing is added to what is served; Playwright is a test
  dependency only. `data-testid` attributes are plain HTML.
- **Vendored council not modified (3):** untouched.
- **Secrets (6) and guarded requests (7):** the instance runs with no keys; the
  simulated model is on loopback, which the SSRF rules allow.
- **Verified, not assumed (9):** this feature turns the manual browser check into an
  automated one. Principle 9's wording is updated in the same pull request to name the
  UI tier.
- **Test-driven (11):** the baseline scenarios describe behaviour that already exists,
  so they cannot fail for lack of product code. They are seen failing first for lack of
  step definitions and harness, and each is then proven able to fail by breaking the
  behaviour once (a mutation check recorded in the pull request).
- **Small, focused changes (10):** one pull request; no product behaviour changes.

## Test strategy

| Requirement | Proof |
|---|---|
| FR-1 | `builder.feature` runs under `pytest` with `pytest-bdd` |
| FR-2, FR-13 | Unit tests of the launcher: free port, readiness wait, startup output in the error |
| FR-3 | Unit test: after the session fixture exits, both ports are closed and the temp files are gone |
| FR-4 | `harness.feature` "The operator's data is untouched": a sentinel database at the default path is byte-identical after the tier runs |
| FR-5 | Manual: `pytest -m "not e2e"` passes in an environment without Playwright |
| FR-6 | Manual: `--headed` opens a window |
| FR-7, FR-9 | Unit tests of the simulated model: each route, default reply, judge parser accepts the reply |
| FR-8 | `harness.feature` "Nothing leaves the machine" |
| FR-10 | `harness.feature` "A failing scenario leaves evidence", using an inner pytest run of a deliberately failing scenario |
| FR-11 | `harness.feature` "A script error fails the scenario" |
| FR-12 | Unit test: the launcher turns Playwright's missing-executable error into the documented message |
| FR-14, FR-15 | Manual, once: a pull request that breaks a baseline behaviour shows a red check with downloadable evidence |
| FR-16 | The six scenarios in `builder.feature` |
| NFR-1, NFR-2 | Measured once locally: wall time, and twenty consecutive runs |

## Risks

- **A role needs a stricter reply than the fixed text.** Contained by T3: a run against
  the simulated model with no browser, before any UI scenario depends on it.
- **Flaky waits on the live view.** Scenarios wait on visible state (an element
  appearing), never on fixed delays; NFR-2 is measured before merging.
- **Browser download in CI is slow.** The job caches the browser by Playwright version.
- **Blocking the merge needs a repository setting.** The job reports a failing check;
  making it required is a branch-protection rule the maintainer enables after the first
  green run.
- **The page depends on something external we did not notice.** FR-8's scenario blocks
  all external hosts, so such a dependency shows up as a failure in this feature.
