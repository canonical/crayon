---
name: dogen-review
description: Surfaces a drafted documentation unit for human review through two modes — record (compact provenance summary + verdict) and review (additionally runs a five-dimension findings review). Records the verdict by calling dogen-record-review.sh for all verdicts — accept seals page SHA-256 hashes, fix/redraft append the note to the steering stream. Never edits the draft. Use when a TA is ready to review a drafted unit.
allowed-tools: Read, Bash, Glob, Grep, AskUserQuestion
---

<objective>
Surface a drafted documentation unit for human review and record the reviewer's
structured verdict — without changing anything the reviewer will publish. The
reviewer chooses one of two modes: **record** (present a compact provenance summary,
then record the verdict) or **review** (additionally run a five-dimension findings
review grounded by re-checking claims against the recorded sources).

- **accept** → call `dogen-record-review.sh --verdict accept` to seal the exact
  draft text (SHA-256 lands on the review record).
- **fix** / **redraft** → call `dogen-record-review.sh --verdict fix|redraft --note`
  to append the note to the ledger's steering stream and record the verdict, so
  it durably steers the next drafting pass.

This skill never edits the draft or runs a build. Regeneration routes back to
dogen-write.
</objective>

<quick_start>
1. Confirm the target unit id. Read `unit.md` and `ledger.md` for the plan,
   signoff, generations, and steering.
2. Read the drafted page(s) under `docs/`.
3. Select the review mode with `AskUserQuestion`: **record** or **review**.
4. Present the provenance summary (both modes).
5. In review mode, run the five-dimension findings review.
6. Elicit the verdict. Call `dogen-record-review.sh --verdict <accept|fix|redraft>` for all verdicts. Then STOP.
</quick_start>

<pipeline>
dogen-plan -> dogen-write -> dogen-review
                            \-> back to dogen-write (fix/redraft)

This skill is the review stage — the last in the loop. On accept, the loop stops.
On fix/redraft, it routes back to the draft-stage skill with the note landed in
the steering stream.
</pipeline>

<workflow>
<step_1 name="Resolve the drafted unit">
Confirm the unit id. Read:

- `.dogen/units/<id>/unit.md` — for `sphinx_target`, `extra_targets`, `sources`,
  intent, audience, and format.
- `.dogen/units/<id>/ledger.md` — the `## signoff` section, the `## steering`
  stream, and the `## generations` section (the latest generation's `file` and
  `sha256` tell you what was drafted).
- The drafted page(s) under `docs/<target>` (and `docs/<extra_target>` for a
  multi-file unit).

If no generation exists in the ledger, the unit was never drafted — route the TA
back to dogen-write.
</step_1>

<step_2 name="Select the review mode">
Ask the reviewer, with `AskUserQuestion`, which mode they want:

- **record** — "I have already read it; just record my verdict." Skips the findings
  review; goes straight to the provenance summary and the verdict.
- **review** — "Do a full review and show me findings." Runs the five-dimension
  findings review before the verdict.

The raw page source is not dumped by default in either mode — offer it only if the
reviewer asks.
</step_2>

<step_3 name="Present the provenance summary">
Load `references/provenance-summary.md` now for the exact field map.

Both modes. Present a human-readable summary from the ledger:

- **Signoff:** author, when, and whether the plan is still the one signed off
  (compare `plan_hash` in the signoff row to `sha256(unit.md)` — if they differ,
  the plan is stale).
- **Latest generation:** model, provider, mode, the page file and its SHA-256.
- **Declared sources vs. actually read:** the declared sources from `unit.md`
  vs. the generation's recorded `context_origins` (if the context report exists
  under `.dogen/staging/<id>/report.md`).
- **Recorded gaps:** any gaps the writer declared.
- **Steering stream:** N entries; quote the latest.
- **Progress state:** derived from the ledger (pending → drafted → reviewed).
</step_3>

<step_4 name="Perform the findings review (review mode only)">
Load `references/review-rubric.md` now for the pre-pass, dimensions, priority tags,
and verification discipline.

Skip entirely in record mode.

**Deterministic pre-pass (before any judgment):** run cheap read-only greps over
the drafted page(s):
- changelog-framing tells ("previously", "now supports", "starting with")
- banned researcher register ("observed", "the fixtures show", "the corpus")
- self-reference openers ("This page describes", "This document")

Each hit is either promoted into the findings as a prioritized finding marked
`(pre-pass)`, or dismissed with a one-line reason.

Then assess the five dimensions, presenting findings grouped by dimension:

1. **writing-approach** (always on, assessed first) — stance contract violations,
   researcher register, implementation identifiers in prose.
2. **source-fidelity** — re-check the draft's concrete claims against the recorded
   sources. Open the files; don't judge only on internal coherence.
3. **completeness** — does the draft satisfy every `## Outline / acceptance` item?
   An objective-check failure is must-fix by definition.
4. **structure-fit** — format hygiene (MyST/rST), cross-page consistency for
   multi-file units, relative link paths resolve from the page's location.
5. **clarity** — sentence-level clarity, jargon, forward references.

Number findings `F-1`, `F-2`, … Each carries: page path, the verbatim offending
text, a concrete suggested action, and a priority tag (must-fix / should-fix / nit).
Ground source-fidelity and completeness by re-checking claims against the recorded
sources.
</step_4>

<step_5 name="Elicit the verdict and record it">
Elicit the reviewer's verdict. In review mode, recommend a verdict from the tally:
any must-fix → fix (or redraft if pervasive); should-fix only → TA's call; clean →
accept. The recommendation is a default, never a decision.

**On accept** — call the deterministic script:

```bash
scripts/dogen-record-review.sh "$UNIT_ID" --verdict accept --note "$REVIEWER_NOTE"
```

The script computes the SHA-256 of the drafted page, writes a review row with
`verdict: accept` and `sealed: <path>:<hash>` to the ledger, and commits with
`Dogen-Phase: review` / `Dogen-Verdict: accept` trailers. Exit 1 if no generation
exists; exit 0 on success.

**On fix / redraft** — call the deterministic script (it appends the note to the
steering stream AND records the verdict in one atomic commit):

```bash
scripts/dogen-record-review.sh "$UNIT_ID" --verdict fix --note "$REVIEWER_NOTE"
```

The script appends a steering row (origin: review) and a review row to the ledger,
then commits with `Dogen-Phase: review` / `Dogen-Verdict: fix` trailers. The note
is exactly what the next drafting pass will read — concrete, actionable, in the
reviewer's own words. Findings are cited by number (`F-2`, `F-5`).

Then route:
- **accept** → `Next: accepted — the publishing commit is yours.` The loop stops.
- **fix** → `Next: /dogen-write — apply the recorded fix.`
- **redraft** → `Next: /dogen-write — re-draft against the recorded steering.`

Quote the `git: committed <sha7>` line (on accept) or note that the steering note
was appended (on fix/redraft). Then STOP: no build, no publish, no edits to the draft.
</step_5>
</workflow>

<edge_cases>
**Unit never drafted:** no `## generations` section in the ledger. Route the TA to
dogen-write to draft first.

**Reviewer wants text edits:** this skill does not edit the draft. The ONE correction
path is: record the change as a fix/redraft verdict (it lands in the steering stream)
and route to dogen-write. Never offer to edit the draft yourself.

**Duplicate accept:** if the latest review row already has `verdict: accept` for the
same draft hash, the unit is already sealed. Surface and stop — nothing needs redoing.

**Reopening an accepted unit:** record a `fix` or `redraft` verdict (append to the
`## reviews` section and the `## steering` section). This reopens the unit; the next
dogen-write pass re-drafts it.

**The plan is stale (unit.md changed after signoff):** surface it in the provenance
summary. The reviewer may want the plan re-approved before judging the draft.
</edge_cases>

<constraints>
<must>
- Offer two selectable modes up front (record vs review) via `AskUserQuestion`.
- Present a human-readable provenance summary in both modes before eliciting a verdict.
- In review mode, run the deterministic pre-pass before judgment, then present
  five-dimension findings grouped by dimension, numbered F-N with must-fix/should-fix/nit tags.
- Ground source-fidelity/completeness findings by re-checking claims against the
  recorded sources.
- On accept, call `dogen-record-review.sh --verdict accept` to seal page hashes and commit.
- On fix/redraft, call `dogen-record-review.sh --verdict fix|redraft --note` to append the
  note to the steering stream and record the verdict in one atomic commit.
- Record the verdict BEFORE any re-draft is invoked.
</must>
<must_not>
- Never run `sphinx-build` or any build — building and publishing are out of scope.
- Never edit the draft, `unit.md`, or any file under `docs/` — the correction path
  is a recorded verdict plus a drafting pass.
- Never suggest the reviewer hand-edit the draft as the way to apply findings.
- Never dump the raw page source into the conversation by default; offer only on request.
</must_not>
</constraints>

<success_criteria>
- [ ] The review mode (record or review) was selected up front.
- [ ] A provenance summary was presented before the verdict.
- [ ] In review mode, the pre-pass and five-dimension findings ran, grounded against
      the recorded sources; in record mode, findings were skipped.
- [ ] On accept, `dogen-record-review.sh --verdict accept` was called and exited 0; the sealed hash was
      quoted.
- [ ] On fix/redraft, the note was appended to the ledger's steering section; the
      routing line pointed to dogen-write.
- [ ] No build was run, no file under `docs/` was edited, and hand-editing the draft
      was never suggested.
</success_criteria>
