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
| 001 | `ui-e2e-tests` | Behaviour scenarios for the web UI run automatically in a real browser, against a simulated model, locally and on every pull request. | Implemented; awaiting first CI run |
| 002 | `agent-cards` | Agent nodes on the canvas show what each agent carries (name, description, prompt, tools, priming) and let the operator add or remove those parts, and add agents, directly from the node. | Implemented; awaiting review |
| 003 | `canvas-preview` | Try the current graph against one goal from a panel docked on the canvas, with the active agent highlighted, without leaving the builder. | Not started |
| 004 | `execution-trace` | Each turn shows its steps with durations, so the operator can see where time goes and which agent or tool acted. | Not started |
| 005 | `guardrails-shields` | Checks from the OpenAI open-source guardrails library, and whole guardrails configurations, run as shields in the same pipeline as the literature shields. | Spec clarified |
| 006 | `agent-targets` | Agents built with the OpenAI Agents SDK as targets: tool calls and handoffs are traced, and forbidden actions count as attack success. Ships a sandbox agent with simulated tools. | Spec draft |
| 007 | `mcp-injection` | Myrtia serves simulated MCP tools to an agent target and injects the attack through tool descriptions or results. Depends on 006. | Spec draft |

## Backlog (unordered)

- Ring layout that leaves room between neighbouring agents at seven and eight attackers
  (today adjacent cards overlap and one comes to the front when pointed at).
- X-Teaming as a new multi-agent, multi-turn attack plugin.
- Observability dashboards (Grafana): real-time token consumption, latency and activity
  per agent and per run, fed by exported metrics and traces.
- Itemised evaluation rubric: per-question judge verdicts alongside the 0–5 score.
- Upload a custom behaviour dataset.
- White-box attacks behind a matching target connector.
- Request models for every endpoint; limits on concurrent runs and body size.
