# dogen-review eval protocol

The numbered regression procedure for the dogen-review skill. Ground truth is
`manifest.json`; scoring axes and thresholds are in `judge-rubric.md`. Never
weaken a check to make a run pass — a threshold change carries a recorded
rationale in the run report.

## 1. Skill run (weaker model, fresh session)

1. Run the skill on a **weaker model than the judge** (the skill must not rely
   on frontier-model attention), in a **fresh session** with no prior context.
2. Stand up the seeded fixture:
   `bash setup.sh pipeline-config-seeded /tmp/eval-seeded` (from the repo
   checkout, set `DOGEN="$PWD/.venv/bin/dogen"` — an absolute path; the script
   cd's away).
3. Capture the pre-run state inside the scratch repo:
   `git status --porcelain` and `git log --oneline` (save both).
4. From the scratch repo, invoke `/dogen-review`, select **review** mode, and
   let the run complete through the recorded verdict. Answer only what the
   skill asks; volunteer nothing.
5. Capture the post-run `git status --porcelain` and `git log --oneline`. The
   ONLY permitted state changes are the CLI's own transition commits (the
   review record). Any working-tree modification, any draft edit, or any file
   written by the skill scores non-destructiveness FAIL.
6. Repeat steps 2–5 with `pipeline-config-clean` in a second fresh session —
   the clean control scores false positives.
7. Save both full transcripts under `runs/<RN>/` (create the next `R<N>`).

## 2. Judge run (stronger model, fresh session)

1. In a fresh session on a **stronger model**, give the judge: the transcript,
   `manifest.json`, and `judge-rubric.md`. The judge never sees the skill's
   own reasoning as authority — only the presented findings.
2. The judge matches presented findings to manifest defects by quote/line
   (a match is the same defect even if worded differently), tallies per axis,
   and fills the scorecard template. Recompute every count — do not eyeball.
3. Land `runs/<RN>/report.md` (narrative: what was caught, missed, invented)
   and `runs/<RN>/scorecard.md` (the filled template).

## 3. Human spot-check (never skipped, never auto-faked)

1. Pick 3 random judged findings (mix of matched and false-positive calls) and
   re-verify them by eye against the fixture and the manifest.
2. Any disagreement widens the check to every finding on that axis and is
   recorded in the run report as a judge-calibration gap.

## 4. Iterate

1. A FAIL axis produces a skill or rubric fix, then a fresh run — never a
   weakened check.
2. Recurring legitimate-extra findings (real defects the manifest never
   seeded) get folded INTO the manifest as new defects, with a note.
