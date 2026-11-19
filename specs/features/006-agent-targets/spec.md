# Spec 006 — Agent Targets

- **Status:** Implemented
- **Issue:** #<tbd>

## Context and goal

Myrtia currently targets single-step chat models and generic HTTP agent endpoints, which means multi-step tool use, agent-to-agent handoffs, and forbidden tool invocations inside an agent runtime are opaque to the operator.

This feature adds native agent targets to Myrtia—shipping a built-in sandbox agent with simulated tools and handoffs—so any attack plugin can target an agent, trace every tool call and handoff live, and count forbidden agent actions as attack success.

## Users

- **AI safety and red-team researcher** — wants to run Myrtia attacks against multi-step tool-using agents and measure whether attacks trigger forbidden tool calls or unsafe handoffs.
- **Model / agent builder** — wants to inspect a complete trace of tool calls, tool outputs, and handoffs during adversarial testing.

## User stories

- **US-1** — As a red-team researcher, I want to select a sandbox agent target in Myrtia so that I can test how existing and new attacks compromise an agent with tools and handoffs.
- **US-2** — As an agent builder, I want every tool call, handoff, and forbidden action executed by the target agent to be emitted as structured run events so that I can audit the exact execution path.

## Functional requirements

- **FR-1** — THE SYSTEM SHALL support an agent target connector kind (`agent_sdk`) that conforms to Myrtia's target connector contract (`generate(prompt) -> Response`) and runs a multi-step agent loop with tools and handoffs.
- **FR-2** — THE SYSTEM SHALL ship a built-in sandbox agent configuration with deterministic simulated tools (such as workspace file read/write, customer lookup, and external message dispatch) and a specialist handoff agent using harmless canary data.
- **FR-3** — WHEN the target agent invokes a tool or hands off to another agent, THE SYSTEM SHALL emit structured trace events (`agent.tool_called`, `agent.tool_responded`, `agent.handoff`) and record the trace on the response metadata.
- **FR-4** — WHEN the target agent executes a forbidden tool or forbidden argument pattern (such as exfiltrating canary secrets or calling restricted administrative tools), THE SYSTEM SHALL emit `agent.forbidden_action` and mark the attempt as an attack success (`forbidden_actions_triggered`).
- **FR-5** — THE SYSTEM SHALL enforce Myrtia's SSRF guard on the agent target's `base_url` and never leak API keys or auth headers in trace events or errors.
- **FR-6** — IF the underlying model endpoint fails or returns an error during an agent turn, THEN THE SYSTEM SHALL return `Status.ERROR` cleanly without crashing the run.
- **FR-7** — WHERE the optional `openai-agents` SDK is installed and configured, THE SYSTEM SHALL allow driving an `openai-agents` `Agent` through the same connector interface and trace hooks.

## Non-functional requirements

- **NFR-1** — The built-in sandbox agent shall execute all tools in memory using benign canary data with zero real filesystem, shell, or external network side effects.
- **NFR-2** — The offline test suite shall run without requiring external API keys or installing optional third-party agent SDKs.

## Edge cases

- The target agent answers directly without calling any tool (completes in 1 turn with empty tool/handoff trace).
- The target agent loops on tool calls until the maximum turn limit (terminates cleanly and returns the partial summary).
- A forbidden action is triggered in turn 1 even if the final text response appears benign (forbidden action still counts as attack success).
- Invalid or blocked `base_url` (rejected by SSRF guard before any outbound call).

## Out of scope

- Executing real host commands or mutating host files from the sandbox agent.
- Serving live external MCP stdio/SSE servers (handled by `007-mcp-injection`).

## Acceptance scenarios

```gherkin
Scenario: Sandbox agent executes a tool call and a handoff traced as structured events  # covers FR-1, FR-2, FR-3
  Given a sandbox agent target backed by a simulated model
  When an attack sends a prompt that triggers a tool call and a specialist handoff
  Then the connector emits "agent.tool_called", "agent.tool_responded", and "agent.handoff"
  And no forbidden action is flagged when only safe tools are used

Scenario: Forbidden tool call by the agent counts as attack success  # covers FR-2, FR-4
  Given a sandbox agent target with forbidden action rules
  When an attack tricks the agent into calling a restricted exfiltration tool
  Then "agent.forbidden_action" is emitted
  And the target connector records the forbidden action as an attack success

Scenario: SSRF guard blocks metadata endpoints on agent target  # covers FR-5
  Given an agent target spec pointing to a cloud metadata address
  When the target connector is built
  Then the SSRF guard rejects the target URL

@e2e
Scenario: Live local model drives the sandbox agent target end-to-end  # covers FR-1, FR-2, FR-3
  Given a live local model endpoint configured for the sandbox agent target
  When a prompt is sent through the agent target connector
  Then the agent completes and returns a valid response
```

## Definition of done

1. Every acceptance scenario passes, and each was seen failing before the code existed.
2. `ruff check backend`, `pytest -m "not e2e"`, `pytest backend/tests_ui`, and the feature's `@e2e` scenario pass.
3. No secrets or real host side effects occur.

## Open questions

- None.

