# Goal dataset catalog

The Runs library accepts one goal per row. Plugins → Goal datasets downloads only
curated CSV files; it does not install packages or execute repository code. Each source
is pinned to a revision and SHA-256 digest in `backend/myrtia/data/goal_datasets.py`.
Downloaded files live in `.data/goal_datasets/` (or `MYRTIA_GOAL_DATA_DIR`) and are
excluded from Git. HarmBench remains bundled and available without a download.

| Dataset | Goals imported | Categories | Source | License |
|---|---:|---|---|---|
| [HarmBench](https://github.com/centerforaisafety/HarmBench) | 278 bundled | SemanticCategory | Bundled text behaviors | MIT |
| [JailbreakBench JBB-Behaviors](https://huggingface.co/datasets/JailbreakBench/JBB-Behaviors) | 100 harmful | 10 categories | Official harmful-behaviors.csv; benign and judge-comparison excluded | MIT |
| [AdvBench](https://github.com/llm-attacks/llm-attacks) | 520 | No upstream category; shown as `advbench` | Official harmful_behaviors.csv | MIT |
| [StrongREJECT](https://github.com/alexandrasouly/strongreject) | 60 | 6 categories | Original small dataset, not the full 313-prompt set | MIT |

Other well-known benchmarks have different semantics:

- [JudgeBench](https://github.com/ScalerLab/JudgeBench) evaluates judges against
  pairs of candidate answers. Its rows are not red-team goals, so it is shown as a
  reference in Plugins rather than offered as a goal download.
- [XSTest](https://github.com/paul-rottger/xstest) includes safe prompts and unsafe
  contrasts for over-refusal testing. Importing the safe prompts into the current
  jailbreak ASR workflow would produce a misleading score; it needs a separate
  over-refusal evaluation mode.

The goal selector filters by dataset, then category and text. Selections from
different datasets can be combined in one run. The backend limits each run to 500
goals, so a full AdvBench run must be split into batches.

Each run stores its purpose and the dataset of every selected goal. Curated dataset
selections default to **Security evaluation**; manually typed goals default to
**Smoke test**, and uploaded goals default to **Unreviewed**. Change the purpose
before launch if that is not appropriate. History and Statistics can filter by
dataset; Statistics and audit exports exclude smoke and unreviewed runs by default.
Historical runs without this metadata stay unreviewed until classified from the
run detail—Myrtia does not infer safety from goal text.
