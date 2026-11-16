# X-Teaming prompt templates

One file per prompt. The **whole file is the prompt** — paste the verbatim block from the
paper into it, replacing the placeholder. No keys, no indentation, no escaping.

Source: X-Teaming, Appendix A.4 (Rahman et al., arXiv:2504.13203, COLM 2025), **CC BY 4.0**
— cite the paper. Committed to git; the raw model outputs a run produces are never
committed. See `../../../../THIRD_PARTY_NOTICES.md`.

| File | Paper block | Keep these `{slots}` |
|---|---|---|
| `planner_system.yaml` | A.4.1 · System Prompt | — |
| `planner_user_first.yaml` | A.4.1 · User Prompt (First Set) | `{target_behavior}` |
| `planner_user_subsequent.yaml` | A.4.1 · User Prompt (Subsequent Sets) | `{target_behavior}` `{previously_generated_strategies}` |
| `planner_plan_revision.yaml` | A.4.1 · Plan Revision (sent under the attacker's system prompt, A.2) | `{target_behavior}` `{old_plan}` `{conversation_history}` `{turn_number}` `{previous_turn_number}` |
| `attacker_system.yaml` | A.4.2 · System Prompt | `{target_behavior}` `{strategy}` `{max_turns}` |
| `attacker_user_first.yaml` | A.4.2 · User Prompt (First Turn) | `{turn_1_conversation_flow}` `{max_turns}` |
| `attacker_user_subsequent.yaml` | A.4.2 · User Prompt (Subsequent Turns) | `{turn_number}` `{previous_turn_number}` `{conversation_history}` `{turn_number_conversation_flow}` |
| `attacker_user_final.yaml` | A.4.2 · User Prompt (Final Turn) | `{conversation_history}` `{final_turn_conversation_flow}` |
| `optimizer_user.yaml` | A.4.3 · User Prompt (the TextGrad loss, applied to the target's reply) | `{score}` `{reason}` `{behavior}` |
| `optimizer_update.yaml` | *Not in the paper* — Myrtia's rewrite step standing in for TextGrad's update (the query rewritten from the loss feedback) | `{query}` `{feedback}` |
| `verifier_system.yaml` | *Not in the paper* — Myrtia's own 1-5 verifier; leave as is | — |

The attacker reply's message is read from a `<conversation>…</conversation>` block, as in
the paper. To tune a prompt without editing these files, set
`MYRTIA_XTEAMING_PROMPTS_FILE` to a YAML of `<file-name-without-.yaml>: |` overrides.
