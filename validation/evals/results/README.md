# Eval results

Every figure in this folder measures skill-following: whether a model driving the five crayon
skills did what the skill text says at that point. None of them measures the quality of a page,
or speed or effort saved; each result says so in `meta.measures`, set to `skill-following`.

`<date>-<lane>-<model>-k<K>-<split>.json` is one clean, complete, paid run of one lane on one model:
K runs of every case in the split, each case's passes out of K, what it cost, the skills
(`meta.skills_sha256`) and the kit (`meta.kit_sha256`) it ran on, and its `decision` block. A new
run adds a file and never edits an old one. Dry, filtered and errored runs go to `raw/`, which is
gitignored. `docs/evals.md` says how to read these files, and `validation/evals/README.md` says how
they are made.

`archive/` keeps the results of the kit before this one, as recorded: an LLM judge graded four of
their checks, their roster is not the current one, the 2026-09-23 and 2026-09-24 files predate
`meta.measures`, and every file names the tool's version as `dogen_version`, the tool's name before
it was renamed crayon. They decide nothing.
