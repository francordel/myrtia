# Third-party code and provenance rules

Myrtia is an independent project. We study PentAGI as a reference and may adopt
parts of it. To keep Myrtia legally clean and commercially usable, every adoption
must follow these rules. **When in doubt, do not copy — reimplement.**

## PentAGI licensing (verified 2026-09-21)

- **Source code: MIT License** (`Copyright (c) 2025 PentAGI Development Team`).
  MIT permits use, copy, modify, distribute, sublicense and sell, **provided the MIT
  copyright + permission notice is retained** in copies or substantial portions.
- An **EULA** overlays acceptable-use terms, but it states that for the source code the
  MIT license prevails in any conflict.
- **Trademark:** "PentAGI" and its branding are NOT licensed. Myrtia must carry no
  PentAGI name, logo, or branding.

## 🚫 The AGPL landmine — hard rule

PentAGI's backend depends on **`github.com/vxcontrol/cloud` v0.9.0** ("VXControl Cloud
SDK"), which is **AGPL-3.0**, licensed with a special exception **only for the official
PentAGI project**. That exception does NOT extend to us.

**Rule:** no file, snippet, or dependency that imports `github.com/vxcontrol/cloud`
(directly or transitively) may enter Myrtia. AGPL-3.0 is network-copyleft and would
force Myrtia's entire service open. Also review the other vxcontrol forks before use:
`vxcontrol/graphiti-go-client`, `vxcontrol/langchaingo` — confirm each is MIT/permissive.

## Adoption checklist (per file/snippet pulled from PentAGI)

1. Confirm the file is MIT (no AGPL imports, direct or transitive).
2. Retain the MIT copyright/permission notice for substantial portions.
3. Record it in the table below: what, from where, license, why.
4. Strip all PentAGI branding/names.
5. Prefer reimplementation over copy for anything small or ambiguous.

## Provenance log

| Myrtia path | Adopted from | License | Notes |
|---|---|---|---|
| `backend/vendor/ares-council/` | Maintainer's own CouncilAttack plugin (ARES Team) | Apache-2.0 (`LICENSE` + `NOTICE` in folder) | Vendored CouncilAttack, authored by the maintainer. Additive, no-op-by-default seams: `set_event_emitter`/`_emit` and `load_goals`. Depends on IBM ARES (`ares-redteamer`, Apache-2.0) as an installed package. No PentAGI code; no `vxcontrol/cloud`. |
| `backend/myrtia/plugins/council_official.py` | ARES `experiments/assets/council_system_contextual_phase0c.yaml` (ARES Team) | Apache-2.0 | Verbatim contextual proposer system prompt from the experimental artifact. |
| `backend/myrtia/plugins/council_prompts.py` | ARES `plugins/ares-council` (ARES Team) | Apache-2.0 | Critic and chairman role instructions adapted for graph agents; placeholder examples removed. |
| `backend/myrtia/plugins/crescendo.py` | Crescendo (Microsoft Research; ARES `ares-pyrit`) | Reimplemented; refs Apache-2.0/MIT | Our own implementation from the technique. Verified: only short, incidental phrases shared with upstream; no substantial copied text. |
| `backend/myrtia/plugins/obfuscation.py`, `garak_probes.py` | garak encoding/probe families (NVIDIA garak) | Reimplemented; garak is Apache-2.0 | Our own implementation of the encoding/probe transforms; garak not imported. |
| `backend/myrtia/plugins/human_jailbreak.py` | Public DAN/AIM-style persona templates (unknown authorship) | Public, unattributed | Widely circulated jailbreak persona wrappers with a `{goal}` slot; documented as public templates, no ownership claimed. |
| `backend/myrtia/plugins/tap.py` | TAP / PAIR (arXiv:2312.02119, 2310.08419) | Reimplemented from the papers | Our own implementation; no upstream code used. |
| _(no PentAGI code adopted)_ | | | Backend is Python; PentAGI (Go) is a pattern reference only. |

## Goal datasets

Myrtia bundles the filtered HarmBench behaviors under `backend/myrtia/data/`.
Additional goal CSVs are fetched only when the operator clicks Download in Plugins.
They are stored under the ignored `.data/goal_datasets/` directory; they are not
redistributed in the repository. Upstream copyrights and MIT license terms apply.
The pinned revision, SHA-256 digest, and exact file URL for each download are in
`backend/myrtia/data/goal_datasets.py`.

| Dataset | Origin | License | Imported portion |
|---|---|---|---|
| HarmBench | [Center for AI Safety](https://github.com/centerforaisafety/HarmBench) | [MIT](https://github.com/centerforaisafety/HarmBench/blob/main/LICENSE) | Bundled filtered text behaviors |
| JailbreakBench | [JBB-Behaviors](https://huggingface.co/datasets/JailbreakBench/JBB-Behaviors) | [MIT](https://huggingface.co/datasets/JailbreakBench/JBB-Behaviors/blob/main/LICENSE) | Harmful behavior goals only |
| AdvBench | [llm-attacks](https://github.com/llm-attacks/llm-attacks) | [MIT](https://github.com/llm-attacks/llm-attacks/blob/main/LICENSE) | `harmful_behaviors.csv` |
| StrongREJECT | [Alexandra Souly et al.](https://github.com/alexandrasouly/strongreject) | [MIT](https://github.com/alexandrasouly/strongreject/blob/main/LICENSE) | 60-row original small dataset |

## Dependency licences (distributed set)

The pip-installable `backend` and the Docker image pull a permissive dependency closure
(MIT / BSD / Apache / PSF / ISC). Two notes for completeness:

- **MPL-2.0 (file-level, non-viral):** `certifi`, `tqdm`, `bidict`, `orjson`. Shipped
  unmodified; MPL obliges sharing changes only to those files, which are not modified.
- **`docutils`** is mixed-licensed (mostly public domain + BSD, with GPL on a few
  peripheral tool files); it arrives transitively via the ARES stack. No AGPL/GPL/LGPL is
  imposed on Myrtia.

See `docs/license-audit.md` for the full audit.
