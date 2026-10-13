# Contributing to Myrtia

Thanks for your interest. Myrtia is an agent-native red-teaming framework for LLMs and
AI agents (see the [README](README.md)). It is **dual-use** — please read
[DUAL_USE.md](DUAL_USE.md) before contributing attack content.

## Development setup

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Run the backend:

```bash
uvicorn myrtia.api.app:app --reload
```

Open `frontend/standalone.html` (zero-build) in a browser, or serve it statically.

## Tests

The suite is split into two tiers (markers in `backend/pyproject.toml`):

```bash
cd backend
pytest -m "not e2e"   # fast, offline — must stay green (CI runs this on every PR)
pytest -m e2e         # needs a live OpenAI-compatible endpoint (local Ollama)
```

Point the e2e tier elsewhere with `MYRTIA_TEST_ENDPOINT` / `MYRTIA_TEST_MODEL`.

## Lint & format

```bash
cd backend
ruff check .      # lint (config in [tool.ruff])
ruff format .     # format
```

CI runs `ruff check` (currently informational) and the offline tests on every push and
pull request to `main`.

## Adding an attack (no core edits — Open/Closed)

Attacks are **auto-discovered**: drop a module in `backend/myrtia/plugins/` that calls
`register(...)` at import time and it shows up — you do not edit the API or any registry
list. A plugin is an ARES-style strategy: a class constructed as
`Strategy(config, target_connector)` exposing `attack()` (and optionally `generate()`),
described to the UI via a `PluginSpec` (`id`, `description`, `config_schema`, `paper`,
`how`, `templates`). To stream per-turn events to the live UI, implement the
`set_event_emitter(emit)` seam (see `plugins/base.py` and existing plugins like
`plugins/direct.py`).

Private/support modules (prefixed with `_`, or the contract base / prompt helpers) are
skipped by discovery.

## Adding a target connector

Target connectors live in `backend/myrtia/connectors/` and honour the `Connector`
protocol in `connectors/base.py` (`generate(prompt) -> Response`, plus `config` and
`tokens`). Wire a new `kind` into `connectors/factory.py`. All outbound requests must be
SSRF-guarded (the factory validates the URL) and must not follow redirects.

## Pull requests

- Keep the offline tests green (`pytest -m "not e2e"`).
- Run `ruff check .` before pushing.
- Never commit secrets (`.env*`, API keys) or real high-sensitivity worked exemplars —
  see [DUAL_USE.md](DUAL_USE.md).
- One focused change per PR where possible.
