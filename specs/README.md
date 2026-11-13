# Specs — how Myrtia is specified

Myrtia is developed spec-first and the specs stay alive next to the code: a change in
behaviour starts as a change in a spec, and when the code ends up different from the
spec, the spec is corrected in the same pull request. Code and specs are both the source
of truth and must agree.

## Layout

```
specs/
  constitution/            stable rules for the whole project (rarely changes)
    mission.md             what we build, for whom, and what we do not build
    tech-stack.md          technologies, conventions and non-negotiable principles
    roadmap.md             feature order: done, next, backlog
  templates/               copy these to start a feature
    spec.md  plan.md  tasks.md
  features/
    NNN-short-name/        one folder per feature, numbered in creation order
      spec.md              what the feature does and why, with acceptance criteria
      plan.md              how it will be built
      tasks.md             checklist of small, verifiable tasks
```

## Flow for a feature

| Step | Output | Rule |
|---|---|---|
| 1. Specify | `spec.md` | What and why only. No stack, architecture or file names. |
| 2. Clarify | `spec.md`, revised | Resolve every `[NEEDS CLARIFICATION]` before planning. |
| 3. Plan | `plan.md` | How: modules, data, contracts, decisions with the rejected alternative. |
| 4. Tasks | `tasks.md` | Small tasks in dependency order, each tied to requirement ids. |
| 5. Implement | tests, then code | One task at a time, test first (red, green, refactor); then stop. |
| 6. Validate | verdict in the PR | Walk every requirement and state what proves it. |

A person reviews the output of every step before the next one starts. Steps 1 to 4 are
done in plan mode: nothing is written until the proposal is approved.

New requirements and bugs enter through step 1: add or correct the requirement in the
spec, then update the plan and add a task. The constitution is only revisited when a
project-wide rule changes.

## Writing requirements

Functional requirements are numbered `FR-1`, `FR-2`, … within a feature and written in
EARS notation so each one is testable:

| Pattern | Template |
|---|---|
| Ubiquitous | THE SYSTEM SHALL `<behaviour>` |
| Event-driven | WHEN `<event>`, THE SYSTEM SHALL `<response>` |
| State-driven | WHILE `<state>`, THE SYSTEM SHALL `<response>` |
| Unwanted behaviour | IF `<condition>`, THEN THE SYSTEM SHALL `<response>` |
| Optional feature | WHERE `<option is active>`, THE SYSTEM SHALL `<response>` |

Every task names the requirements it covers, and every requirement is covered by a test.

## Acceptance scenarios

Acceptance criteria are written as Gherkin scenarios in the spec and copied into a
`.feature` file under `backend/tests/features/`, where `pytest-bdd` runs them:

```gherkin
Scenario: A run stores the token usage of the target
  Given a finished run against a local target
  When the backend restarts
  Then the run history still shows the token usage
```

The scenario is written before the code and must fail first. Scenarios that drive a
whole run against a live model are the end-to-end tier (`@e2e`); the rest run offline.

UI behaviour has its own tier: scenarios in `backend/tests_ui/features/` run in a real
browser against a simulated model (`pytest backend/tests_ui`). A manual check written in
the spec is only for what no scenario can reach, such as a setting in the repository
host.

## Tracking

- One GitHub issue per feature, linking to its folder. The pull request closes it.
- `tasks.md` is the fine-grained checklist; `roadmap.md` is the order of features.
- Specs that must stay private (unpublished research, dual-use detail) are not written
  here; see `DUAL_USE.md`.
