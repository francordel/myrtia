# Spec 011 — Agent Skills Attacks

- **Status:** Implemented
- **Issue:** #<tbd>

## Context and goal

AI assistants and coding agents increasingly load modular "skills" (`SKILL.md` packages containing YAML metadata, natural-language instructions, and companion resources) to perform multi-step tasks. Because models treat loaded skill text as trusted operational guidance, attackers can embed prompt injections inside skills to trigger unauthorized actions such as data exfiltration, file tampering, or policy bypasses.

This feature adds a self-contained Agent Skills attack suite to Myrtia, covering the canonical attack patterns from the literature (including `SKILL-INJECT`-style contextual injections, metadata poisoning, companion-resource indirect injections, and cross-skill hijacking), so operators can test whether any target model in Myrtia is vulnerable without needing an external agent runtime.

## Users

- **AI safety and red-team researcher** — wants to benchmark how susceptible a target model is to skill-based prompt injections across famous literature patterns.
- **Model builder / defender** — wants to verify whether guardrails and system prompts prevent a model from executing unauthorized tool calls instructed by a loaded skill.

## User stories

- **US-1** — As a red-team researcher, I want to run canonical Agent Skills attacks against any target model in Myrtia so that I can measure its attack success rate on skill-embedded threats.
- **US-2** — As a defender, I want to see which simulated tool calls and actions the target model attempted after reading a poisoned skill so that I can diagnose why the model complied or refused.

## Functional requirements

- **FR-1** — THE SYSTEM SHALL provide an Agent Skills attack plugin that tests a target model against poisoned skill packages (`SKILL.md` metadata and instructions) using a self-contained simulated tool-calling loop.
- **FR-2** — THE SYSTEM SHALL include the canonical skill attack families from the literature:
  1. **Direct skill override** (explicit instruction override inside skill steps),
  2. **Contextual / subtle task-disguised injection** (`SKILL-INJECT`-style unauthorized step blended into a legitimate workflow),
  3. **YAML metadata poisoning** (malicious directives hidden in skill frontmatter fields such as `description`),
  4. **Companion resource indirect injection** (malicious payload returned when the model reads a referenced skill resource), and
  5. **Cross-skill hijack** (a loaded skill attempting to redirect or misuse another trusted tool or skill).
- **FR-3** — WHEN executing a skill attack against a target model, THE SYSTEM SHALL supply a benign user task, the loaded skill context, and simulated safe tools (such as workspace file access, network/message dispatch, and command execution) using harmless canary data.
- **FR-4** — WHEN the target model requests a simulated tool call during the loop, THE SYSTEM SHALL record the tool name and arguments as structured run events, return a deterministic simulated tool response, and continue the turn until completion or turn limit.
- **FR-5** — WHEN the target model attempts a forbidden action or unauthorized tool call defined by the attack scenario, THE SYSTEM SHALL flag the unauthorized action in the run outcome alongside the judge evaluation.
- **FR-6** — WHERE an operator selects specific skill attack variants or configures the number of turns, THE SYSTEM SHALL run only the selected variants within the configured turn budget.
- **FR-7** — IF the target model endpoint fails or returns an invalid response during the skill loop, THEN THE SYSTEM SHALL record the error clearly without leaking secrets and mark the attempt as failed without crashing the run.
- **FR-8** — WHEN `skill.*` events (`skill.loaded`, `skill.tool_called`, `skill.tool_responded`, `skill.forbidden_action`) arrive in the live UI trace, THE SYSTEM SHALL render them with human-readable role labels, tool details, and distinct blocked/warning styling for `skill.forbidden_action`.

## Non-functional requirements

- **NFR-1** — All built-in skill payloads and simulated resources shall use benign canary identifiers (never real credentials, real external URLs, or worked harmful completions).
- **NFR-2** — Skill attack execution shall work against any chat/OpenAI-compatible target model already supported by Myrtia, with no external MCP or agent-SDK runtime required.

## Edge cases

- The target model ignores tool definitions and answers only in plain text (must finish cleanly without infinite looping).
- The target model emits malformed tool-call arguments (must be handled gracefully and recorded).
- The target model refuses the injected instruction while completing the benign task (must be scored as defended / unsuccessful attack).
- Maximum turn limit is reached before the target model produces a final answer (must terminate cleanly and record partial trace).

## Out of scope

- Executing real shell commands, real network requests, or real filesystem mutations on the host machine.
- Serving live MCP protocol servers (covered by the separate MCP injection feature).
- Scanning external third-party skill marketplaces.

## Acceptance scenarios

```gherkin
Scenario: Target model complies with a subtle SKILL-INJECT payload  # covers FR-1, FR-2, FR-3, FR-4, FR-5
  Given a target model that follows instructions in loaded skill files
  When the operator runs the Agent Skills attack with the contextual injection variant
  Then the run trace records the loaded skill and the simulated unauthorized tool call
  And the run flags the forbidden action alongside the judge verdict

Scenario: Target model refuses a poisoned skill and completes only the benign task  # covers FR-1, FR-3, FR-5
  Given a target model that ignores injected directives in skill metadata
  When the operator runs the Agent Skills attack with the YAML metadata poisoning variant
  Then no forbidden tool call is flagged
  And the run finishes with an unsuccessful attack outcome

Scenario: Companion resource indirect injection triggers on resource read  # covers FR-2, FR-4
  Given a skill that instructs the model to inspect a companion resource
  When the target model reads the companion resource and receives the injected payload
  Then the simulated resource read and any subsequent tool call are recorded in the run events

@e2e
Scenario: Live local model is evaluated against the Agent Skills attack suite  # covers FR-1, FR-2, FR-3, FR-4, FR-5
  Given a live local model endpoint configured as the target
  When the operator runs the Agent Skills attack
  Then the run completes and stores the structured skill-loop events and judge score
```

## Definition of done

1. Every acceptance scenario passes, and each was seen failing before the code existed.
2. `ruff check backend`, `pytest -m "not e2e"`, and the feature's scenarios pass.
3. No real secrets or external network calls are made by simulated tools.

## Open questions

- None (all initial scope decisions resolved).

