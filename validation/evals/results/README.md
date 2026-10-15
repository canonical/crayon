# Eval results

Every figure in this folder measures skill-following: whether a model driving the five dogen
skills did what the skill text says at that point. None of them measures the quality of a page,
or speed or effort saved. Summaries written from now on say so in `meta.measures`, set to
`skill-following`. The files from 2026-09-23 and 2026-09-24 predate the key and are kept exactly
as recorded; this README labels them instead.

`<date>-<lane>-<model>.json` is one clean run. A file ending in `-k3.json` holds three runs, with
each case's passes out of three. Baselines are per (candidate, judge) pair, and a new run adds
files and never edits old ones. Partial, dry, errored and re-graded runs go to `raw/`, which is
gitignored. `docs/evals.md` says how to read these files, and `validation/evals/README.md` says
how they are made.
