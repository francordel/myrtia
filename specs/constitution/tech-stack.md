# Tech stack and principles

## Stack

| Layer | Choice |
|---|---|
| Language | Python 3.11+ (uv provisions 3.12) |
| Packaging | uv workspace: `backend` and `backend/vendor/ares-council` |
| API | FastAPI: REST for run control, one WebSocket per run for live events |
| Persistence | SQLite behind the run store |
| Frontend | `frontend/standalone.html`: a single zero-build file, plain HTML, CSS and JavaScript |
| Attack plugins | ARES-style strategies, auto-discovered from `backend/myrtia/plugins/`; adapters wrap attacks from ARES, garak and PyRIT |
| Tests | pytest with `pytest-bdd` (Gherkin `.feature` files); offline tier (`-m "not e2e"`), end-to-end tier (`-m e2e`) and UI tier in a real browser (`backend/tests_ui`, Playwright) |
| Lint and format | ruff (line length 100) |
| Delivery | `uv run myrtia`, plus a Docker image and Compose file |
| Licence | Apache-2.0; third-party origins recorded in `THIRD_PARTY_NOTICES.md` |

`docs/architecture.md` records the original architecture decisions and the event schema.

## Principles (non-negotiable)

Every spec, plan and task must respect these. A feature that needs to break one must
change this file first, in its own pull request.

1. **The spec leads.** Behaviour changes start in a spec. Code and spec are kept in
   agreement in the same change.
2. **Zero-build frontend.** The UI stays a single file served as-is. No bundler, no
   framework, no build step.
3. **The vendored council is not modified.** `backend/vendor/ares-council` keeps the
   published attack logic so reported numbers stay reproducible. Only additive, no-op by
   default integration seams are allowed.
4. **Open for extension, closed for modification.** New attacks and connectors are new
   modules that register themselves. Adding one must not require editing core code.
5. **Clean boundaries.** The core, the attack plugins and the storage layer talk through
   explicit contracts. Plugins import nothing from the API layer.
6. **Secrets never leave in the clear.** API keys and auth headers are redacted in logs,
   in the database, in REST responses and in live events.
7. **Outbound requests are guarded.** Every connector and proxy validates its URL
   against the SSRF rules (loopback and LAN allowed, link-local and cloud metadata
   blocked) and does not follow redirects.
8. **No private dual-use artefacts in git or in the Docker build context.** Files
   matching `*.private.*` and worked harmful completions stay out.
9. **Verified, not assumed.** A change is done when `ruff check backend` reports nothing,
   `pytest -m "not e2e"` is green, and, for UI behaviour, the UI scenarios pass in the
   browser tier.
10. **Small, focused changes.** One feature or fix per pull request, touching only what
    it needs.
11. **Test-driven.** Code is written test first: a failing test, then the minimum code
    that passes it, then refactoring. Acceptance criteria are written as Gherkin
    scenarios and executed with `pytest-bdd`; the scenarios that exercise a whole run
    are the end-to-end tests.
12. **Traceable by default.** Anything an agent, a tool, a target or a judge does during
    a run is emitted as a structured event and stored. A feature that adds behaviour to
    a run also adds the events needed to see it.

## Conventions

- English everywhere in the repository.
- Events are the contract between backend and UI: new live behaviour is a new or
  extended event type, documented in the feature plan.
- Error messages shown to the operator say what failed and why; they do not echo
  secrets.
- UI text and controls follow the design tokens already defined in `standalone.html`,
  in both the dark and the light theme.
