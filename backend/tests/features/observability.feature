Feature: Observability metrics
  Myrtia exports what its models and runs are doing as metrics, in a standard format,
  so a dashboard can show tokens, latency and activity in real time (spec 008).

  Background:
    Given a clean metrics registry

  # --- metrics address ---------------------------------------------------------
  Scenario: The metrics address serves the Prometheus text format
    When I request the metrics address
    Then the reply status is 200
    And the reply is Prometheus text
    And the reply documents the metric "myrtia_model_calls_total" as a "counter"
    And the reply documents the metric "myrtia_model_call_duration_seconds" as a "histogram"
    And the reply reports the build version

  Scenario: The metrics address follows the access token
    Given the access token "obs-test-token" is configured
    When I request the metrics address
    Then the reply status is 401
    When I request the metrics address with the token as a bearer credential
    Then the reply status is 200
    When I request the metrics address with the token as a query parameter
    Then the reply status is 401

  # --- model calls -------------------------------------------------------------
  Scenario: A successful model call is counted with its tokens
    Given a "judge" connector for model "sim-judge"
    And the model replies with 12 prompt tokens and 30 completion tokens
    When the connector is called once
    Then the metrics count 1 "ok" call for role "judge" and model "sim-judge"
    And the metrics count 12 "prompt" tokens for role "judge"
    And the metrics count 30 "completion" tokens for role "judge"
    And the latency distribution for role "judge" holds 1 observation

  Scenario: A failed model call is counted as an error
    Given a "judge" connector for model "sim-judge"
    And the model endpoint answers with an HTTP error
    When the connector is called once
    Then the metrics count 1 "error" call for role "judge" and model "sim-judge"
    And the latency distribution for role "judge" holds 1 observation
    And the metrics hold no tokens

  Scenario: A reply without usage data records no tokens
    Given a "judge" connector for model "sim-judge"
    And the model replies without usage data
    When the connector is called once
    Then the metrics count 1 "ok" call for role "judge" and model "sim-judge"
    And the metrics hold no tokens

  Scenario Outline: Each caller is labelled with its role
    Given a "<declared>" connector for model "sim-model"
    And the model replies without usage data
    When the connector is called once
    Then the metrics count 1 "ok" call for role "<role>" and model "sim-model"

    Examples:
      | declared | role    |
      | judge    | judge   |
      | defense  | defense |
      | target   | target  |
      | default  | aux     |

  Scenario: A call can state the role of the agent making it
    Given a "default" connector for model "sim-model"
    And the model replies without usage data
    When the connector is called once as "chairman"
    Then the metrics count 1 "ok" call for role "chairman" and model "sim-model"

  Scenario: The judge, the shields and the graph agents declare their roles
    Given the model replies without usage data
    When the graded judge, a shield's helper and a graph attacker each call their model
    Then the metrics count 1 "ok" call for role "judge" and model "m-judge"
    And the metrics count 1 "ok" call for role "defense" and model "m-shield"
    And the metrics count 1 "ok" call for role "attacker" and model "m-agent"

  # --- runs and events ---------------------------------------------------------
  Scenario: A run is counted from start to finish
    When the run "r1" of attack "crescendo" starts
    Then 1 run of attack "crescendo" is active
    And the metrics count 1 started run of attack "crescendo"
    When the run "r1" finishes with status "succeeded"
    Then 0 runs of attack "crescendo" are active
    And the metrics count 1 finished run of attack "crescendo" with status "succeeded"
    And the run duration distribution for attack "crescendo" holds 1 observation

  Scenario: A finish without a start does not go negative
    When the run "ghost" finishes with status "failed"
    Then the metrics count 1 finished run of attack "unknown" with status "failed"
    And no attack has a negative number of active runs

  Scenario: Judge verdicts are counted by score
    Given the run "r1" of attack "tap" has started
    When the judge scores 5, 5, 2 and 9 in run "r1"
    Then the metrics count 2 verdicts with score "5" for attack "tap"
    And the metrics count 1 verdicts with score "2" for attack "tap"
    And the metrics count 1 verdicts with score "invalid" for attack "tap"

  Scenario: Shield actions are counted
    When the shield "self-reminder" is applied and the shield "perplexity-filter" blocks
    Then the metrics count 1 "applied" action of shield "self-reminder"
    And the metrics count 1 "blocked" action of shield "perplexity-filter"

  Scenario: Every event published on the bus is counted by type
    When a "turn.started" event is published on the event bus twice
    Then the metrics count 2 events of type "turn.started"

  # --- per-run series ----------------------------------------------------------
  Scenario: Calls inside a run feed its per-run series
    Given a plugin whose attack calls the target once
    And the model replies with 7 prompt tokens and 5 completion tokens
    When the orchestrator executes the run "obs-run" with that plugin
    Then the metrics count 1 "ok" call for role "target" and model "sim-target"
    And the run "obs-run" has 1 call and 12 tokens for role "target"

  Scenario: Only the most recent runs keep per-run series
    Given the per-run limit is 2
    When model calls are recorded for runs "r1", "r2" and "r3" in that order
    Then the metrics hold per-run series for "r2" and "r3"
    And the metrics hold no per-run series for "r1"

  Scenario: A model call outside any run stays out of the per-run series
    Given a "preflight" connector for model "sim-model"
    And the model replies with 3 prompt tokens and 4 completion tokens
    When the connector is called once
    Then the metrics count 1 "ok" call for role "preflight" and model "sim-model"
    And the metrics hold no per-run series at all

  # --- safety ------------------------------------------------------------------
  Scenario: Secrets and addresses never reach the metrics
    Given a connector with an API key, a custom auth header and an endpoint address
    And the model replies with 1 prompt tokens and 1 completion tokens
    When the connector is called with a prompt
    Then the metrics contain neither the key, the header, the address nor the prompt

  Scenario: A metrics failure does not break the model call
    Given a "judge" connector for model "sim-judge"
    And the model replies without usage data
    And recording metrics fails
    When the connector is called once
    Then the call still returns the model's reply

  Scenario: Label values are escaped
    When a call is recorded for a model named with a quote, a backslash and a line break
    Then the metrics text keeps one sample per line and escapes the name

  # --- dashboard and stack -----------------------------------------------------
  Scenario: The dashboard only queries exported metrics
    Given the provisioned dashboard
    Then every metric it queries is exported by Myrtia

  Scenario: The dashboard has the promised panels
    Given the provisioned dashboard
    Then it has panels for runs, tokens, latency, calls, judge scores, shields, events and one run

  Scenario: The console is told where the dashboard is
    Given the dashboard address is one where nothing answers
    When the console asks where the dashboard is
    Then it gets the dashboard's address and the command that starts it
    And it is told the dashboard is not reachable

  Scenario: The console is told when the dashboard answers
    Given the dashboard address is one that answers
    When the console asks where the dashboard is
    Then it is told the dashboard is reachable

  Scenario: The dashboard address can be switched off
    Given the dashboard address is switched off
    When the console asks where the dashboard is
    Then it is told there is no dashboard

  Scenario: The dashboard links back to the console
    Given the provisioned dashboard
    Then it has an "Open Myrtia" link whose address is filled in when the stack starts
    And the Compose file fills it in from the console's address setting

  Scenario: The stack is local and anonymous
    Given the observability Compose file
    Then Grafana and the collector are published on the loopback address only
    And Grafana is viewable without logging in and its login form is disabled
    And Grafana sends no analytics and checks for no updates
