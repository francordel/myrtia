Feature: Run traces
  Each run can be emitted as an OpenTelemetry trace: a tree of steps (run, goal, turn,
  model call) with durations, content and verdicts, so it can be followed and audited
  outside the console (spec 009).

  Background:
    Given a clean tracing state

  # --- switching it on ---------------------------------------------------------
  Scenario: Tracing is off by default
    Given tracing has not been switched on
    When a run with one goal and one turn calls its target once and finishes
    Then no step is recorded
    And tracing reports that it is off

  Scenario: Tracing reports where it exports
    When tracing is configured on with the address "http://127.0.0.1:4318"
    Then tracing reports that it is on, exporting to "http://127.0.0.1:4318"

  Scenario: Missing packages do not stop Myrtia
    Given the tracing packages are not installed
    When tracing is configured on with the address "http://127.0.0.1:4318"
    Then tracing reports that it is off because the packages are missing
    And a run with one goal and one turn still completes its model call

  Scenario: A blocked address switches tracing off
    When tracing is configured on with the address "http://169.254.169.254"
    Then tracing reports that it is off because the address is not allowed

  Scenario: The console is told whether tracing is on
    Given tracing is on
    When the console asks about observability
    Then it is told tracing is on

  # --- shape of a trace --------------------------------------------------------
  Scenario: A run becomes one trace of nested steps
    Given tracing is on
    When a run with one goal and one turn calls its target once and finishes
    Then there is one trace with the steps "run", "goal", "turn" and "chat"
    And each step is nested under the one before
    And the run step carries the run's identifier, attack, target model and status "succeeded"

  Scenario: A model call records role, model, tokens and outcome
    Given tracing is on
    When a run with one goal and one turn calls its target once and finishes
    Then the "chat" step has role "target" and model "sim-target"
    And the "chat" step reports 12 input tokens and 30 output tokens
    And the "chat" step is not an error

  Scenario: A failed model call is an error step
    Given tracing is on
    And the model endpoint fails
    When a run with one goal and one turn calls its target once and finishes
    Then the "chat" step is an error

  Scenario: A failed run marks its trace as an error
    Given tracing is on
    When a run fails with the reason "ValueError: boom"
    Then the "run" step is an error with the reason "ValueError: boom"
    And the run step carries the run's identifier, attack, target model and status "failed"

  Scenario: A single-shot run hangs its calls under the run
    Given tracing is on
    When a run without goals or turns calls its target once and finishes
    Then the "chat" step is nested directly under the "run" step

  Scenario: A goal that is never closed is closed by the end of the run
    Given tracing is on
    When a run opens a goal and a turn and finishes without closing them
    Then every step of the trace has ended

  Scenario: A model call outside any run is not traced
    Given tracing is on
    When a model is called outside any run
    Then no step is recorded

  # --- events and verdicts -----------------------------------------------------
  Scenario: Events are attached to the step they happened in
    Given tracing is on
    When a run with one goal and one turn emits a proposal and a verdict of 4
    Then the "turn" step holds the events "proposal.created" and "judge.scored"

  Scenario: The verdict is recorded on the turn
    Given tracing is on
    When a run with one goal and one turn emits a proposal and a verdict of 4
    Then the "turn" step has the judge score 4

  # --- content -----------------------------------------------------------------
  Scenario: Content is included by default
    Given tracing is on
    When a run with one goal and one turn calls its target once and finishes
    Then the "chat" step holds the prompt and the reply
    And the "goal" step holds the goal's text

  Scenario: Content can be switched off
    Given tracing is on without content
    When a run with one goal and one turn emits a proposal and a verdict of 4
    Then no step or event holds the prompt, the reply, the goal or the proposal
    But the "chat" step has role "target" and model "sim-target"
    And the "turn" step has the judge score 4

  Scenario: Long content is cut and marked
    Given tracing is on with a content limit of 50 characters
    When a run with one goal and one turn calls its target with a 500-character prompt
    Then the prompt in the "chat" step is cut and the step is marked as truncated

  Scenario: Keys never reach a trace
    Given tracing is on
    When a run whose target uses an API key and a custom auth header echoes a key in its reply
    Then no step or event contains the key or the header name

  # --- safety ------------------------------------------------------------------
  Scenario: A tracing failure does not break the model call
    Given tracing is on
    And recording a step fails
    When a run with one goal and one turn calls its target once and finishes
    Then the model call still returned the model's reply

  Scenario: Trace data stays out of the repository and the image
    Then the trace store keeps its data in a Docker volume, not in a repository folder
    And Myrtia's own data folder is ignored by git
    And the observability files are left out of the application image

  # --- stack and dashboard -----------------------------------------------------
  Scenario: The stack has a local trace store
    Then the stack's trace store is published on the loopback address only
    And the trace store sends no usage reports
    And Grafana is provisioned with the trace store

  Scenario: The traces dashboard lists runs and shows one
    Then the "Myrtia traces" dashboard lists recent runs and shows the timeline of a chosen trace
    And the overview and the traces dashboards link to each other and to the console
