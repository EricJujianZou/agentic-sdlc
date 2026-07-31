# Memorization probe (bench5)

Per PLAN.md: for every frozen instance, ask each subject model — given ONLY
the issue text (no repo, no tools) — to name the files the fix touched.

## Method

- One single-turn query per (instance, model) via local `claude -p
  --model <model>` from an empty directory (no repo context, tools
  irrelevant for a single text turn).
- Prompt gives the repo name + problem statement verbatim and asks for a
  JSON list of predicted file paths (up to 10).
- Scoring against gold-patch file paths (from `diff --git` headers):
  - A predicted path matches a gold path if the normalized full path is
    equal, or the predicted path is a suffix of the gold path (>= 2
    components) — tolerates missing repo-root prefixes.
  - **Mentioned-file exclusion:** gold files whose path (or basename)
    appears verbatim in the problem statement are excluded from scoring —
    naming them is reading comprehension, not memorization.
  - `probe_recall` = matched unscorable-excluded gold files / scorable gold
    files. Instances where ALL gold files are mentioned in the issue are
    recorded `scorable=false` and excluded from probe-conditioned analyses.
- **High-probe definition (pre-registered before results seen):** an
  instance is high-probe for the primary sensitivity analysis if EITHER
  model achieves probe_recall >= 0.5 on scorable files.

## Outputs

- `probe_results.json` — per (instance, model): predicted files, matches,
  probe_recall, scorable flag, raw model output.
- Committed before the pilot verdict is acted on; primary analysis is
  repeated excluding high-probe instances per PLAN.md.
