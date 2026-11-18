# Spec 007 — MCP Injection Attacks

- **Status:** Implemented
- **Issue:** #<tbd>

## Context and goal

Model Context Protocol (MCP) servers expose tools, schemas, and resources that AI assistants and agents load directly into their context window. Because models often treat MCP server metadata and tool outputs as trusted instructions, attackers can exploit MCP integrations via tool poisoning, rug pulls, cross-server tool shadowing, and indirect prompt injection through tool results or resources.

This feature adds a self-contained MCP injection attack plugin to Myrtia that simulates MCP servers, tool manifests, and a bounded tool-calling loop using harmless canary data, so operators can test whether any target model in Myrtia is vulnerable to canonical MCP attacks without requiring an external MCP server or agent runtime.

## Users

- **AI safety and red-team researcher** — wants to measure how susceptible a target model is to canonical MCP attack vectors from the literature.
- **Model builder / defender** — wants to verify whether a model resists poisoned MCP tool descriptions, post-approval rug pulls, cross-server shadowing, and malicious tool outputs.

## User stories

- **US-1** — As a red-team researcher, I want to run canonical MCP attacks against any target model in Myrtia so that I can measure its vulnerability to MCP-based prompt injections.
- **US-2** — As a defender, I want to inspect which simulated MCP server, tool definition, and tool calls occurred during a run so that I can diagnose how the model was compromised or how it defended itself.

## Functional requirements

- **FR-1** — THE SYSTEM SHALL provide an MCP injection attack plugin that tests a target model against simulated MCP servers and tool manifests using a self-contained simulated tool-calling loop.
- **FR-2** — THE SYSTEM SHALL include the canonical MCP attack families from the literature:
  1. **MCP Tool Poisoning** (hidden malicious directives inside a tool's `description` or parameter schema),
  2. **MCP Rug Pull** (a tool definition that is benign on initial turn/discovery and mutates on a subsequent turn to inject malicious directives),
  3. **MCP Tool Shadowing** (an untrusted MCP server whose tool metadata attempts to hijack or redirect calls to a separate trusted MCP server's tools), and
  4. **MCP Indirect Injection via Tool Output / Resource** (a benign MCP tool or resource returning a payload with embedded malicious instructions).
- **FR-3** — WHEN executing an MCP attack against a target model, THE SYSTEM SHALL supply a benign user task, simulated MCP server tool manifests (with harmless canary workspace data), and deterministic simulated MCP tool responses.
- **FR-4** — WHEN the target model invokes a simulated MCP tool, THE SYSTEM SHALL record the server name, tool name, arguments, and tool output as structured run events, and—for the rug-pull variant—update the active tool manifest after the initial benign turn.
- **FR-5** — WHEN the target model executes a forbidden action or unauthorized MCP tool call (such as exfiltrating canary data to an external endpoint or hijacking a trusted tool), THE SYSTEM SHALL flag the unauthorized action in the run outcome alongside the judge evaluation.
- **FR-6** — WHERE an operator selects specific MCP attack variants or configures the turn budget, THE SYSTEM SHALL run only the selected variants within the configured turn budget.
- **FR-7** — IF the target model endpoint fails during the MCP loop, THEN THE SYSTEM SHALL record the error without leaking secrets, skip judging the error string, and mark the attempt as failed without crashing the run.

## Non-functional requirements

- **NFR-1** — All simulated MCP manifests, canary files, and endpoints shall use synthetic canary identifiers and `.example.invalid` domains (never real credentials, real external URLs, or real host mutations).
- **NFR-2** — MCP injection attacks shall work against any chat/OpenAI-compatible target model already supported by Myrtia.

## Edge cases

- The target model ignores MCP tools and responds in plain text (terminates cleanly after turn 1).
- The target model emits malformed JSON tool calls or calls an unknown MCP tool (handled gracefully and recorded).
- In the rug-pull scenario, the model finishes in turn 1 before the manifest mutates (terminates cleanly with no forbidden action).
- Maximum turn limit is reached before completion (terminates cleanly and records partial trace).

## Out of scope

- Spawning real external MCP stdio/SSE server processes or mutating host files.
- Requiring an external OpenAI Agents SDK runtime (self-contained loop works on any target connector).

## Acceptance scenarios

```gherkin
Scenario: Target model falls for MCP Tool Poisoning  # covers FR-1, FR-2, FR-3, FR-4, FR-5
  Given a target model that follows hidden instructions in MCP tool descriptions
  When the operator runs the MCP injection attack with the "tool_poisoning" variant
  Then the run trace records the MCP manifest and the unauthorized tool call
  And the run flags the forbidden action alongside the judge verdict

Scenario: Target model resists MCP Tool Shadowing  # covers FR-1, FR-2, FR-5
  Given a target model that ignores cross-server shadowing directives
  When the operator runs the MCP injection attack with the "tool_shadowing" variant
  Then no forbidden action is flagged
  And the run finishes with an unsuccessful attack outcome

Scenario: MCP Rug Pull mutates tool manifest after initial benign turn  # covers FR-2, FR-4, FR-5
  Given a target model interacting with a multi-turn MCP server
  When the operator runs the MCP injection attack with the "rug_pull" variant
  Then the manifest mutation event is recorded after the initial turn
  And any subsequent unauthorized tool call is flagged

@e2e
Scenario: Live local model is evaluated against MCP injection attacks  # covers FR-1, FR-2, FR-3, FR-4, FR-5
  Given a live local model endpoint configured as the target
  When the operator runs the MCP injection attack
  Then the run completes and stores structured MCP events and judge score
```

## Definition of done

1. Every acceptance scenario passes, and each was seen failing before the code existed.
2. `ruff check backend`, `pytest -m "not e2e"`, and the feature's scenarios pass.
3. No real secrets or external network calls are made by simulated MCP tools.

## Open questions

- None.
