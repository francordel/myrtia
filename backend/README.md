# Myrtia backend

Python backend that hosts ARES-compatible attack plugins (CouncilAttack first),
drives a run, and streams the deliberation live over a WebSocket. See
`../docs/architecture.md`.

## Layout

- `myrtia/events/` — typed `Event`/`EventType` (the live-view contract) + async bus
- `myrtia/plugins/` — ARES-compatible plugin contract + registry; `council.py` adapter
- `myrtia/connectors/` — factory building ARES connectors from a Myrtia target spec
- `myrtia/orchestrator/` — drives a run, bridges the (blocking) strategy to the event bus
- `myrtia/hitl/` — PENDING_APPROVAL gate (`request`/`resolve`)
- `myrtia/store/` — in-memory run store (SQLite later)
- `myrtia/api/` — FastAPI: REST control + `/runs/{id}/events` WebSocket

## Run (dev)

```bash
# from the repo root: venv + Python + Myrtia + the vendored CouncilAttack plugin
uv run myrtia --reload
# without uv (Python 3.11+), from backend/:
#   pip install -e . -e vendor/ares-council && uvicorn myrtia.api.app:app --reload
# launching attacks also needs a reachable OpenAI-compatible endpoint (Ollama/vLLM/hosted)
```

Then:

```bash
curl localhost:8000/health
curl localhost:8000/plugins
curl -X POST localhost:8000/runs -H 'content-type: application/json' -d '{
  "attack_id": "council",
  "attack_config": {"council_models": ["gemma3:12b"], "use_borda": true, "use_chairman": true},
  "target": {"kind": "openai_chat", "base_url": "http://127.0.0.1:11434/v1", "model": "gpt-oss:120b"},
  "goals": ["<behaviour>"]
}'
# subscribe to ws://localhost:8000/runs/<run_id>/events for the live deliberation
```

## Status

Backend loop is proven end-to-end with a fake plugin (run.started -> proposal ->
vote -> judge -> run.finished, results stored). Remaining for the MVP: real smoke run
of `ares-council` against a reachable endpoint, the `on_event` seam in the plugin for
per-turn events, and the React UI.
