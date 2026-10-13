# Dual-use disclosure

Myrtia is an **adversarial security-testing framework** for large language models and AI
agents. It generates adversarial prompts and evaluates whether a target model resists them,
so that model builders and defenders can find and fix safety failures. This is the same
purpose as IBM ARES, NVIDIA garak, Microsoft PyRIT, HarmBench and promptfoo.

## Intended use

- Evaluating models and agents **you own or are explicitly authorized to test**.
- Academic and industrial **AI safety / red-teaming research**.
- Building and measuring **defenses** (guardrails, filters, alignment).

Not for producing, distributing, or operationalizing harmful content against systems or
people you are not authorized to test. Using Myrtia does not make an unlawful act lawful.

## What ships in this repository

- **Behaviour goals**: the public HarmBench behaviour list (`data/harmbench_behaviors.csv`),
  the standard benchmark used across the field. These are *requests*, not solutions.
- **Attack templates**: framing/persona templates with a `{goal}` slot filled at run time
  (`human_jailbreak.py`, `garak_probes.py`). No worked harmful content is embedded.
- **Content-free scaffolds**: `contextual_jailbreak.py` uses benign placeholder
  demonstrations, not real harmful exemplars.
- **Council contextual prompt (Phase 2)**: the public build keeps the paper's structure,
  mutators, and **real 5/5 templates**, but the two highest-sensitivity categories (a
  genocide-denial and a child-harassment behaviour) are represented by **lower-sensitivity
  5/5 behaviours** (a vehicle-theft example and a fossil-fuels-vs-renewables op-ed). No
  high-sensitivity worked exemplar is committed here.

## What does NOT ship here (private, opt-in)

The artifact-faithful Phase 2 proposer — the one with all five real worked examples that
produced the reported results — is **not in version control**. It is loaded only when the
operator points an environment variable at their own private copy:

```bash
export MYRTIA_COUNCIL_PHASE2_FILE=/path/to/council_system_contextual_phase2.yaml
```

Accepted formats: raw prompt text, or a YAML `system_prompt: |` block (e.g. the
`ares-private` artifact). Files matching `*.private.txt` / `*.private.yaml` are gitignored.
Keep such copies access-controlled and do not publish them.

## Responsible release

- Model outputs and successful attacks are treated as sensitive; do not redistribute worked
  harmful completions.
- Operators are responsible for the legality of their testing in their jurisdiction and for
  having authorization for every target.
- Report issues or concerns via the repository's issue tracker.

Licensed under Apache-2.0. Provided for authorized security research; no warranty.
