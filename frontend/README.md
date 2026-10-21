# Myrtia frontend

A single, zero-build page: `standalone.html`. It is plain HTML + vanilla JS with no
framework, no bundler and no install step. The backend serves it at `/` (same origin
as the API and the WebSocket), so there is nothing to build or proxy.

## Run

Start the backend and open the app it serves:

```bash
uv run myrtia --reload   # from the repo root
# then open http://127.0.0.1:8000/
```

The page POSTs a run to `/runs` and connects to `/runs/{id}/events` (WebSocket) to
render the deliberation live: proposals, cross-critiques, Borda vote, chairman
synthesis, the target response and the judge score, grouped by goal and turn.

## Layout

- `standalone.html` — the whole app (styles, canvas builder, event stream, history,
  statistics, assistant). One file, edited directly.
- `icon*.png` — brand marks, served from `/assets/{name}`.

An earlier React + Vite scaffold was removed (issue #29): it was never wired up, and
the single-file page is the shipped UI.
