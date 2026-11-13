# Observability: metrics and the Grafana dashboard

Myrtia exports what its models and runs are doing as metrics, and ships an optional
dashboard that shows them in real time. Spec: `specs/features/008-observability-metrics`.

## What you get

- `GET /metrics` on Myrtia itself, in the Prometheus text format. Always on, no extra
  dependency, nothing to configure.
- An optional stack (Prometheus and Grafana in Docker) with the data source and the
  **Myrtia overview** dashboard already provisioned.

The dashboard answers, while runs are in flight:

| Question | Panel |
|---|---|
| Is anything running, and how did runs end? | Active runs, Finished runs, Finished runs by status |
| What is this costing? | Tokens, Tokens per minute by role, Tokens by model |
| Which model is slow? | Model latency by role (median and 95th percentile), Mean latency by model |
| Is an endpoint failing? | Failed calls, Calls per minute by model and outcome |
| How are attacks landing? | Judge score distribution, Shield actions |
| What is one run doing? | Selected run: tokens, calls and model time by role (pick it in the **Run** filter) |

## Start it

You need Docker (Docker Desktop or Colima) for the dashboard; Myrtia itself runs as usual.

1. Start Myrtia:

   ```bash
   uv run myrtia
   ```

2. In another terminal, from the Myrtia folder, start the dashboard (the first time it
   downloads two images):

   ```bash
   docker compose -f compose.observability.yaml up -d
   ```

3. In the console, press **Dashboard** in the header. The dashboard opens in a new tab;
   **Open Myrtia**, at the top of the dashboard, brings you back. You can also open
   <http://localhost:3000/> directly.

4. Launch a run. The panels fill within a few seconds and refresh every five.

There is no login: Grafana is a read-only viewer bound to `127.0.0.1`, and so is
Prometheus (<http://localhost:9090/>).

If the dashboard is not running, **Dashboard** says so and shows the command of step 2
instead of opening an empty tab.

Myrtia in Docker as well:

```bash
MYRTIA_SCRAPE_TARGET=ollama:8000 docker compose -f compose.yaml -f compose.observability.yaml up
```

(`ollama` is the service that publishes Myrtia's port in `compose.yaml`.)

Stop it with `docker compose -f compose.observability.yaml down`; add `-v` to also delete
the stored metrics.

| Setting | Default | Meaning |
|---|---|---|
| `MYRTIA_SCRAPE_TARGET` | `host.docker.internal:8000` | Where Prometheus finds Myrtia (`host:port`) |
| `MYRTIA_URL` | `http://localhost:8000` | Where the dashboard's **Open Myrtia** link leads |
| `GRAFANA_PORT` | `3000` | Grafana's port on this machine |
| `PROMETHEUS_PORT` | `9090` | Prometheus's port on this machine |
| `MYRTIA_METRICS_RUNS` | `20` | How many recent runs keep per-run series (set on Myrtia) |
| `MYRTIA_GRAFANA_URL` | `http://localhost:3000` | Where the console's **Dashboard** control leads (set on Myrtia); `off` hides it |

Notes:

- **Another port.** `uv run myrtia --port 8010` needs both addresses changed:

  ```bash
  MYRTIA_SCRAPE_TARGET=host.docker.internal:8010 MYRTIA_URL=http://localhost:8010 docker compose -f compose.observability.yaml up -d
  ```

- **Another Grafana port.** With `GRAFANA_PORT=3001`, start Myrtia with
  `MYRTIA_GRAFANA_URL=http://localhost:3001` so **Dashboard** finds it.
- **Check it is collecting.** <http://localhost:9090/targets> must show the `myrtia`
  target as `UP`. `DOWN` means the address in `MYRTIA_SCRAPE_TARGET` is wrong or Myrtia
  is not running.
- **Linux.** A container cannot reach a server bound to the host's `127.0.0.1`. Run
  Myrtia in Docker too (command above), or start it with `--host 0.0.0.0` on a machine
  whose firewall keeps that port private.
- **Access token.** With `MYRTIA_TOKEN` set, `/metrics` needs the token as a bearer
  credential (`Authorization: Bearer …`) or in `X-Myrtia-Token`; it is not accepted in
  the URL. Mount a file holding the token into the Prometheus container and uncomment
  the `authorization` block in `observability/prometheus/prometheus.tmpl.yml`.
- **To edit dashboards**, start Grafana with `GF_AUTH_ANONYMOUS_ORG_ROLE=Admin` and save
  your copy; the provisioned dashboard itself is read-only and is changed in git.

## Metrics

| Metric | Type | Labels |
|---|---|---|
| `myrtia_build_info` | gauge | `version` |
| `myrtia_model_calls_total` | counter | `role`, `model`, `outcome` (`ok`, `error`) |
| `myrtia_model_call_duration_seconds` | histogram | `role`, `model` |
| `myrtia_model_tokens_total` | counter | `role`, `model`, `kind` (`prompt`, `completion`) |
| `myrtia_runs_started_total` | counter | `attack` |
| `myrtia_runs_finished_total` | counter | `attack`, `status` |
| `myrtia_runs_active` | gauge | `attack` |
| `myrtia_run_duration_seconds` | histogram | `attack` |
| `myrtia_judge_scores_total` | counter | `attack`, `score` (`0`–`5`, `invalid`) |
| `myrtia_defense_actions_total` | counter | `defense`, `action` (`applied`, `blocked`) |
| `myrtia_events_total` | counter | `type` |
| `myrtia_run_model_calls_total` | counter | `run`, `attack`, `role` |
| `myrtia_run_tokens_total` | counter | `run`, `attack`, `role`, `kind` |
| `myrtia_run_model_seconds_total` | counter | `run`, `attack`, `role` |

`role` is who called the model: `target`, `judge`, `defense`, `preflight`, `attacker`,
`chairman`, or `aux` for any other helper model.

## How it is built

- `GET /observability` tells the console where the dashboard is and whether it
  answers. The server checks because the page's content policy only lets it talk to
  Myrtia itself.
- `backend/myrtia/telemetry.py` is the registry. It is fed by the connectors (every
  `generate()` reports its call) and by the event bus (every published event), so a new
  attack plugin is measured without writing any metrics code.
- Counters start at zero with the process; they are not rebuilt from stored runs. The
  dashboard's totals therefore read "since Myrtia started".
- A run id is unbounded, so it is a label only for the most recent runs
  (`MYRTIA_METRICS_RUNS`); older runs lose their per-run series and stay in the totals.
- No prompt, response, goal, API key, header name or endpoint address is ever a label.
- A metrics failure never breaks a model call or a run.

## Limits

- Tokens are counted when the model endpoint reports usage; an endpoint that does not
  report it shows calls and latency only.
- Model calls an attack makes from threads it starts itself, or through a client other
  than Myrtia's connectors (for example inside the vendored council), appear in the
  totals only if they go through a Myrtia connector, and may miss the per-run series.
- Metrics only: traces and log shipping are not part of this feature.

## Adding a metric

1. Add a scenario to `backend/tests/features/observability.feature` and see it fail.
2. Declare the metric in `CATALOG` in `telemetry.py` and record it.
3. If the dashboard uses it, edit `observability/grafana/dashboards/myrtia-overview.json`;
   a test fails if the dashboard queries a metric that is not declared.
