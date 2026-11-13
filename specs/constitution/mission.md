# Mission

## Why Myrtia exists

The mission is to make language models and AI agents safer. To make them safer, their
weaknesses have to be tested, measured and understood.

Strong red-teaming backends already exist: IBM ARES, NVIDIA garak and Microsoft PyRIT,
among others. What is missing is a front end that brings them together. Each one is
driven from its own command line and configuration, and what an attack actually did is
buried in its own log format. Myrtia is that front end: one interface that runs those
backends as plugins and shows clearly what happened in every run, step by step and agent
by agent.

## What Myrtia is

Myrtia is an open-source red-teaming workbench for LLMs and AI agents. From one web
interface, an operator can:

- **Run existing attacks.** Classic single-turn attacks with no agents (direct requests,
  jailbreak templates, encoding and obfuscation, payload splitting, prompt injection),
  multi-turn attacks (crescendo, adaptive attacker loops) and multi-agent attacks.
  Attacks from other frameworks are wrapped as plugins and launched the same way.
- **Design new multi-agent attacks.** On a canvas, the operator places attacker agents,
  wires how they cooperate and edits each agent's model, prompt and tools. A council in
  which attackers propose, cross-critique and vote is one such design, shipped as a
  preset; it is one attack among many, not what Myrtia is.
- **Test defences.** Guardrails and filters ("shields") are evaluated in the same
  pipeline as the attacks, so attack and defence are measured with the same numbers.
- **See everything.** Every prompt, response, tool call, vote and judge verdict is
  streamed live and stored. Traceability and observability are a core feature: an
  operator must be able to tell which agent did what, in what order, how long it took
  and what it cost.
- **Measure.** A judge model grades each response, and runs are stored so attack success
  can be compared across models, attacks, defences and behaviour themes.

Myrtia runs locally by default: one command, local models, no API key and no data
leaving the machine. Hosted model endpoints are supported as targets and as agents.

## Who it is for

- **AI safety and red-team researchers** who need reproducible experiments and
  comparable success-rate numbers across attack families.
- **Model builders and defenders** who test models, agents and guardrails they own or
  are authorised to test.
- **Reviewers and contributors** from research groups and the open-source security
  community, who must be able to audit the code and add attacks, targets and defences
  as plugins.

## In scope

- Adversarial testing of LLMs and LLM-based agents, with and without attacker agents.
- Plugin adapters for existing red-teaming backends and for new attacks.
- Target connectors for OpenAI-compatible and other chat and agent endpoints, local or
  hosted.
- Defences evaluated alongside attacks.
- Graded judging, attack-success-rate analytics and run history.
- Tracing and observability of agent activity, timing and token use.

## Out of scope

- Network penetration testing or offensive security operations. The target is always a
  model or an agent, never a network or a host.
- Replacing the backends it integrates. Myrtia hosts and visualises them; it does not
  fork their attack logic.
- Publishing worked harmful completions or high-sensitivity exemplars (see
  `DUAL_USE.md`).
- Testing systems without authorisation.

## What good looks like

- A new user reaches a first live run with one command and local models.
- An attack from any integrated backend is launched, watched and measured the same way
  as a native one.
- For any run, an operator can reconstruct what each agent did and why the judge scored
  it as it did.
- Every run can be reproduced from its stored configuration.
- An external reviewer can read a spec, find the code that implements it, and run the
  tests that prove it.
