# Licence audit — attack pool and distributed dependencies

Scope: the attack plugins, the vendored council, the goal datasets, and the dependency
closure of what Myrtia actually distributes (the pip-installable `backend` and the Docker
image). This is a technical review of what is in the repository and the image, not a
legal opinion.

Date: 2026-11-16. Branch: `docs/license-audit`.

## Verdict

**Clean to distribute, no strong copyleft (no AGPL/GPL/LGPL/SSPL) in the distributed
set.** Everything shipped is permissive (MIT / BSD / Apache / PSF / ISC) or weak
file-level copyleft (MPL-2.0, non-viral). Three housekeeping gaps to close and one
design question about the Docker image.

## What we distribute vs. what the user installs

| Set | Contents | Who ships it |
|---|---|---|
| **Distributed** | `backend` core deps + the vendored `ares-council` (which pulls full ARES, `ares-redteamer`) | Us — in the repo and the Docker image |
| **Pack-only** | garak, PyRIT and their deps | The end user, on their machine (install from the console); we never redistribute them |
| **Dev-only** | pytest, ruff, playwright, … | Nobody — not shipped |

The licence question only bites on the **distributed** set; pack-only licences are the
upstream projects' responsibility and we depend on them optionally.

## Findings

### 1. Distributed dependency closure — 144 packages, all permissive bar two notes

- **No AGPL / GPL / LGPL / SSPL** anywhere in the closure.
- **`docutils`** is the only strong-copyleft hit: it is mixed-licensed (mostly public
  domain + BSD, with GPL on a few peripheral tool files). Low risk and very widely
  redistributed (Debian etc.), but note it. It arrives transitively (ARES stack).
- **MPL-2.0 (file-level, non-viral):** `certifi`, `tqdm`, `bidict`, `orjson`. Fine to
  ship unmodified; MPL only obliges you to share changes to *those files*, which we don't
  make.
- Everything else: MIT / BSD-3 / Apache-2.0 / PSF / ISC.

### 2. The Docker image bundles all of ARES (size + positioning, not licensing)

The Dockerfile installs `-e backend/vendor/ares-council`, which depends on
`ares-redteamer` (full ARES, 37 declared deps). So the image pulls a ~144-package ML
stack — `torch`, `transformers`, `streamlit`, `sentence-transformers`, `scikit-learn`,
`ibm-cos-sdk`, `matplotlib`, … Licence-clean, but:
- it makes the image large, and
- it contradicts the "core runs with zero ARES; ARES is an optional pack" positioning in
  the README/AGENTS. In the image, ARES is not optional.

**Question for you:** keep the council in the image (convenient, heavy), or make it an
opt-in pack there too (lean image, matches the stated architecture)?

### 3. Vendored council licence notice — RESOLVED

The council is the maintainer's own Apache-2.0 code. A `LICENSE` (Apache-2.0) and a
`NOTICE` were added to `backend/vendor/ares-council/`; the maintainer sets the copyright
holder line in the NOTICE.

### 4. Provenance log — RESOLVED

`THIRD_PARTY_NOTICES.md` lists only the council. Several plugins describe themselves in
their header as a "port of" an upstream, but are reimplementations:
- `crescendo.py` — "port of the ARES Crescendo strategy"
- `obfuscation.py` — "port of the ARES Encoding strategy" (garak encoding probes)
- `human_jailbreak.py` — "mirrors ARES ares-human-jailbreak"
- `garak_probes.py` — "garak-family probes"

Verified by text comparison: these share only short, incidental phrases with the upstream
packages (a few ≥60-char windows with PyRIT's Crescendo YAML and the public DUDE/DAN
template) — **no substantial copied text**. They are our own code. Action: add a
provenance row for each stating "reimplemented from <source>, <licence>", so the "port"
language in the headers is backed by the log. (X-Teaming, spec 010, is already recorded.)

### 5. `council_prompts.py` references a private repo by name — maintainer-owned

The council is the maintainer's own work, so the `ares-private` artifact is theirs and
the provenance is clear. Only open question: whether the `ares-private` *name* should
appear in a public repo (cosmetic).

### 6. Human-jailbreak templates — RESOLVED (documented)

`human_jailbreak.py` uses public DAN/AIM-style persona wrappers (widely circulated, no
clear author or licence). Low risk, but the honest move is to document them as public
templates of unknown authorship rather than imply ownership.

### 7. Clean areas (no action)

- **Datasets** (HarmBench, JailbreakBench, AdvBench, StrongREJECT): all MIT, with origin,
  pinned revision and SHA-256 recorded in `goal_datasets.py`. Fetched on demand, not
  redistributed.
- **Packs**: garak (Apache-2.0), PyRIT (MIT), ARES (Apache-2.0) — permissive, and
  user-installed, so not redistributed by us. Their own unlicensed transitive deps
  (`avidtools`, `mistralai` carry no metadata licence) are the user's install, not ours.
- **X-Teaming** (spec 010): reimplemented from the paper (CC BY 4.0); the authors' repo is
  unlicensed and is not used. Recorded in `THIRD_PARTY_NOTICES.md`.

## Suggested actions, in order

1. Add `LICENSE` (+ `NOTICE`) to `backend/vendor/ares-council/`. *(obligation)*
2. Complete the `THIRD_PARTY_NOTICES.md` provenance table (items 4). *(cheap, removes
   ambiguity)*
3. Confirm the `ares-private` reference (item 5).
4. Document the human-jailbreak templates' provenance (item 6).
5. Decide the Docker/ARES question (item 2).
6. Optionally note `docutils`/MPL deps in `THIRD_PARTY_NOTICES.md` for completeness.

None of these blocks distribution today; 1 and 2 are the ones worth doing before the next
public release.
