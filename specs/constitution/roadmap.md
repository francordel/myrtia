# Roadmap

Order of features. A feature moves to **Done** when its pull request is merged and its
spec is validated. Detailed history before specs were adopted lives in `BACKLOG.md` and
`docs/audit-log.md`.

## Done (before specs)

- Core loop: orchestrator, event bus, WebSocket live view, run store on SQLite.
- Attack plugins: classic single-turn attacks, multi-turn attacks and multi-agent
  attacks (council, council-crescendo), with adapters for ARES, garak and PyRIT.
- Graph builder: preset topologies and a custom canvas for multi-agent attacks.
- Run history, statistics dashboard, CSV and report export, shields.

## Next

| # | Feature | Summary | Status |
|---|---|---|---|
| 001 | `agent-cards` | Agent nodes on the canvas show what each agent carries (name, description, prompt, tools, priming) and let the operator add or remove those parts, and add agents, directly from the node. | Not started |
| 002 | `canvas-preview` | Try the current graph against one goal from a panel docked on the canvas, with the active agent highlighted, without leaving the builder. | Not started |
| 003 | `execution-trace` | Each turn shows its steps with durations, so the operator can see where time goes and which agent or tool acted. | Not started |

## Backlog (unordered)

- Browser-driven end-to-end scenarios for the UI, written in Gherkin like the backend
  ones, so canvas and live-view behaviour is tested automatically.
- X-Teaming as a new multi-agent, multi-turn attack plugin.
- Observability dashboards (Grafana): real-time token consumption, latency and activity
  per agent and per run, fed by exported metrics and traces.
- Itemised evaluation rubric: per-question judge verdicts alongside the 0–5 score.
- Upload a custom behaviour dataset.
- White-box attacks behind a matching target connector.
- Request models for every endpoint; limits on concurrent runs and body size.
