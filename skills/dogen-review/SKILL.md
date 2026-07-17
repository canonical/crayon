---
name: dogen-review
description: Surfaces a drafted documentation unit for human review through two selectable modes — record, which presents a compact provenance summary then records the reviewer's verdict, and review, which additionally runs a four-dimension findings review (source-fidelity, completeness, structure-fit, clarity) with each finding tagged must-fix, should-fix, or nit and claims re-verified against the recorded sources — then records the structured verdict through a single delegating `dogen review --verdict --note` call. An accept verdict seals the exact draft text; a fix or redraft verdict automatically lands the note in the unit's steering stream for the next pass. Runs no Sphinx build and does not dump the raw page source by default. Never edits the draft or any file. Use when a TA is ready to review a drafted unit.
allowed-tools: Read, Bash, Glob, Grep, AskUserQuestion
---

<objective>
Surface a drafted documentation unit for human review and record the reviewer's
structured verdict — without changing anything the reviewer will publish. The
reviewer chooses one of two modes up front: **record** (present a compact provenance
summary, then record the verdict — the lean path) or **review** (additionally run a
generalized four-dimension findings review, grounded by re-checking claims against
the recorded sources, and present it before the verdict). Both modes read the unit's
sidecars and the drafted page(s) — in the unit's format, MyST or rST; a
multi-file unit's whole target set — and may optionally consult a top-level
`optional-guidance/` directory (house style, framework, or syntax guides) when judging
the draft, present the provenance summary, elicit the
reviewer's judgment, and record it as the required `dogen review --verdict --note`, advancing
progress to `reviewed`. The verdict is structured (v1): **accept** seals the exact
draft text (its hash lands on the review record — the second provable bookend);
**fix** and **redraft** automatically append the note to the unit's steering stream,
so the correction durably steers the next dogen-write pass — it never lives only in
the conversation. This skill holds judgment; the core holds the gate and the commit
seam. It never runs `sphinx-build` (D-13) and never edits the draft or any file —
regeneration routes back to dogen-write. The raw page source is not presented by
default; it is offered only if the reviewer asks. `Write` and `Edit` are excluded
from its tool surface so that posture is enforced at the manifest (D-14/D-18). See
`../README.md` for the shared family contract, glossary, and status vocabulary.
</objective>

<quick_start>
1. Confirm the target unit id and check its current state: it must already have been
   drafted. `dogen unit show <id> --json --latest` gives the state in one lean read
   (the latest generation only —
   older passes' read-lists stay on disk); if it was never drafted, dogen review
   will refuse with `not_drafted` — route the TA back to dogen-write first.
2. Read the unit's sidecars under `.dogen/units/<id>/` (`unit.md`,
   `provenance.yaml`, `progress.yaml`) and the drafted page(s) under `docs/` —
   the `sphinx_target` plus every `extra_targets` entry for a multi-file unit.
   Read them even though they are not dumped into the conversation — you need
   them for the provenance gap and (in review mode) the findings.
3. Select the review mode with `AskUserQuestion` (BLOCKING): **record** (just record
   my verdict) or **review** (do a full findings review first). Do NOT run
   `sphinx-build` or any build — building and publishing are out of dogen's scope; the
   merger owns them (D-13).
4. Present the provenance summary (workflow step 3, both modes). Load
   `references/provenance-summary.md` now for the exact field map.
5. In review mode only, run the findings review (workflow step 4). Load
   `references/review-rubric.md` now for the dimensions, priority tags, grounding
   rule, and layout.
6. Elicit the reviewer's verdict and record it via
   `dogen review <id> --verdict accept|fix|redraft --note "…"` (workflow step 5).
   Then STOP — the reviewer owns any manual edits and the publishing.
</quick_start>

<pipeline>
dogen-plan -> dogen-write -> dogen-review

This skill is the review stage — the last in the loop. It consumes a drafted unit
(the MyST at `docs/<sphinx_target>` plus the `provenance.yaml` / `progress.yaml`
sidecars) and produces a recorded structured review (`dogen review --verdict
--note`, advancing `progress -> reviewed`; the CLI's commit seam records the
transition). Routing rules:

- A fix/redraft verdict routes back to dogen-write with the frozen referral line
  (`Next: /dogen-write — apply the recorded fix.` for a fix; `… — re-draft
  against the recorded steering.` for a redraft). Recording the verdict IS the
  routing act — corrections reach the draft only through that recorded verdict and
  a dogen-write pass, never through anyone editing the draft mid-loop.
- The loop STOPS here: no build or publish. The human owns publishing (and any
  post-accept polish they make as the output's owner — outside the loop).
- This skill has no `Write` or `Edit` tool.
</pipeline>

<workflow>
<step_1 name="Resolve the drafted unit">
Confirm the unit id. Read `dogen unit show <id> --json --latest` (the lean
projection — the latest generation plus `generations_count`; older passes'
read-lists stay on disk) and confirm the unit has been drafted. If progress is below `drafted`, `dogen
review` will refuse with `not_drafted` (reason code) — surface that and route the TA
back to dogen-write to draft first. Read `unit.md` (for the `sphinx_target`,
any `extra_targets`, `sources`, intent, audience — the `format` field says which
markup the page(s) use), `provenance.yaml` (the signoff — and any
`signoff_history` of superseded acts — the steering stream, and the latest
generation, including its `context_origins`, `gaps`/`gaps_note`, per-page
`files` digests, and commit stamps), and every drafted page of the unit's set
under `docs/` with `Read`. Read them fully — they ground the provenance gap and
the findings — but do not paste them into the conversation.
</step_1>

<step_2 name="Select the review mode">
Ask the reviewer, with `AskUserQuestion` (BLOCKING), which mode they want:

- **record** — "I have already read it; just record my verdict." Skips the findings
  review; goes straight to the provenance summary and the verdict.
- **review** — "Do a full review and show me findings." Runs the four-dimension
  findings review before the verdict.

This is the up-front branch; it replaces any dump of the source into the
conversation. The raw page source is not presented by default in either mode —
offer it only if the reviewer asks ("show me the source").

**After a `fix` verdict (re-review default):** when a unit returns for review after
a recorded `fix`, the default is a **scoped re-review** — verify the recorded fix
landed and run a **regression spot-check** of just the touched sections — not a
fresh full pass. A **full four-dimension re-run** happens only on explicit request;
there is no auto-escalation, even on a freshly surfaced must-fix (D-05). Mirror the
record→review escalation idiom below (no re-invocation, just branch): default to
the scoped re-review, and widen to the full four-dimension re-run only when the TA
asks for it.
</step_2>

<step_3 name="Present the provenance summary">
Both modes. Load `references/provenance-summary.md` now. Present a human-readable
provenance summary: the signoff (author, when, and whether the plan is still the
one signed off); the provider, mode, and model of the latest generation; the
declared `sources` versus the `context_origins` the writer actually read (with
their commit stamps — the gap is itself review-relevant); any recorded `gaps` the
writer could not verify; the steering stream; and the current progress state. This
surfaces the audit sidecar the TA otherwise never sees, and it feeds
source-fidelity's declared-vs-read check.
</step_3>

<step_4 name="Perform the findings review">
**Review mode only** (skip entirely in record mode). Load
`references/review-rubric.md` now. Assess **dimension 0 — the objective check —
first**: does the draft satisfy the unit's reader problem and every
`## Outline / acceptance` item? An objective-check failure is **must-fix by
definition** — the severity floor, pinned to the existing must-fix tag and never
downgraded to should-fix or nit, however small the surface edit looks. Then assess
the four dimensions — source-fidelity, completeness, structure-fit, clarity — and
present the findings **grouped by dimension** in the conversation, one line per
finding, each tagged must-fix, should-fix, or nit per the rubric's priority mapping
(label each finding with its page path when the unit spans several and quote the
diverging lines; structure-fit judges each page against its own format's hygiene,
and a multi-file unit additionally gets the rubric's cross-page consistency check,
which dimension 0's objective check relies on for multi-target units). Ground the
findings: for source-fidelity and completeness, re-check the draft's concrete claims
against the recorded sources and context origins themselves (open the files; the
generation's commit stamps say which version was read) — do not judge the draft only
on its internal coherence. For structure-fit and clarity, if the repo has a top-level
`optional-guidance/` directory (house style guides, framework or syntax references), optionally
consult any files relevant to this unit — a draft that contradicts a documented house
convention is a legitimate finding. The absence of the `optional-guidance/` directory is never a
blocker. Quote the offending draft text and give a concrete suggested action. A clean
dimension shows `(none)`; a not-assessed one shows its reason. The findings block is
presented in-conversation only — it is never written to a file. The priority tags are a
review-findings axis only; keep the CLI reason codes and progress states surfaced verbatim (D-03).
</step_4>

<step_5 name="Elicit the verdict and record it">
Elicit the reviewer's structured judgment of the draft and record it via `Bash`:

```bash
dogen review "$UNIT_ID" --verdict "$VERDICT" --note "$REVIEWER_NOTE" --json
```

The three verdicts and what recording each one does (v1):

- **accept** — the draft is approved as-is. The CLI seals the exact draft text: its
  SHA-256 lands on the review record, so what was accepted is provable later.
- **fix** — a specific, bounded correction is needed. The CLI appends the note to
  the unit's steering stream; the next dogen-write pass **applies the recorded
  fix**. Say "apply the recorded fix", never "re-draft".
- **redraft** — the draft needs a fresh pass from scratch. Same steering append;
  the next dogen-write pass **re-drafts** against it. `fix` and `redraft` record
  the note identically — the only difference is this wording and the verdict.

The note should therefore be written to steer: concrete, actionable, in the
reviewer's own words — it is exactly what the next drafting pass will read.
**Record the verdict BEFORE any re-draft happens** — the recorded verdict is the
routing act; a correction that lives only in this conversation steers nothing
and leaves the audit trail empty.

**Quote-heavy notes — prefer `--note-file -`.** When the verdict note contains
quotes, a `::`, or spans several lines, pass it on stdin instead of fighting
shell quoting: `--note-file -` reads the whole note from stdin (a path reads that
file), mirroring `unit edit --body-file -`. Exactly one of `--note` / `--note-file`
is required — giving both, or neither, is a `bad_input` refusal. Example:

```bash
printf '%s' "$REVIEWER_NOTE" | dogen review "$UNIT_ID" --verdict "$VERDICT" --note-file - --json
```

Read the `--json` result and surface it. Route off the machine token `next_id`,
translated into the loop's **frozen referral line** (the exact strings live in
`../README.md`'s routing table) — always the slash form, a definite imperative:

- after a **fix** verdict: `Next: /dogen-write — apply the recorded fix.`
- after a **redraft** verdict: `Next: /dogen-write — re-draft against the recorded steering.`
- after **accept**: `Next: accepted — the publishing commit is yours.`
- on `re_sign`: the plan changed since signoff — re-approve it first (offer the
  folded `dogen unit edit … --re-sign`), then `/dogen-write`.

**Never parrot the raw `next` line to the TA** — it speaks CLI, and the TA drives
skills (quote it only if they ask what the CLI said). If the JSON carries
`unapplied_steering: true` on an accept, warn plainly: a correction recorded
after the last draft was sealed over without being drafted — confirm the TA
means to accept over it. Quote the `git: committed <sha7> — …` line (the JSON's
`commit` field) so the transcript carries the review commit's hash. Then STOP:
no build, no publish, no edits. A `not_drafted` reason means the unit was never
drafted — route back to dogen-write. An `already_accepted` reason means this
exact draft is already sealed by an identical accept (nothing was recorded) —
surface that plainly; there is nothing to redo.
</step_5>
</workflow>

<edge_cases>
**Unit never drafted (`not_drafted`):** `dogen review` refuses. Surface it and route
the TA to dogen-write to draft first.

**Routing a `fix`/`redraft` back to staging — the two scaffolding helpers.** When
a verdict sends the unit back to dogen-write, the writer re-stages under
`.dogen/staging/<id>/`; two read-only-by-default helpers end the round-3 manual
`mkdir` fumble. `dogen staging plan <id>` prints the expected
`handoff/<relpath>` tree and marks each page ✓ staged / missing (`--scaffold`
creates only the missing placeholders — never clobbering a staged draft). `dogen
report template <id>` prints a valid, unit-aware `report.yaml` skeleton
pre-filled from the unit's declared sources (`--write` lands it, `--force` to
replace a non-empty one). Point the writer at these instead of hand-building the
handoff tree or the report — never suggest deleting a staged draft to fix layout.

**Reviewer picked record but now wants findings:** offer to switch to review mode and
run the four-dimension findings review before recording the verdict. No re-invocation
needed — just branch into step 4.

**Reviewer asks to see the raw source:** present the page source (in its own
format, MyST or rST) on request — it is not dumped by default, but offering it
when asked is the intended discretion.

**Reviewer wants text edits:** this skill does not edit the draft, and neither
does the reviewer mid-loop. The ONE correction path is: record the change as a
`fix`/`redraft` verdict (it lands in the steering stream automatically) and
route to dogen-write to apply it. Never offer to make the edits yourself, and
never suggest the reviewer paste or hand-edit the draft as the way to apply
findings — an unrecorded correction steers nothing and is invisible to any
future audit. (After an **accept**, the human owns the output and may of course
polish it as part of their publishing work — that is outside the loop.)

**Duplicate accept (`already_accepted`):** the CLI refused because the latest
sealed accept already covers this identical draft. Nothing was recorded and
nothing needs redoing — surface it and stop.

**Reopening an accepted unit (post-accept iteration — no new verb):** there is no
separate reopen verb. Post-accept iteration is the existing `review --verdict
fix|redraft` → `dogen-write draft` path. The `already_accepted` guard blocks
re-drafting a sealed unit, so you must record the `fix` (or `redraft`) verdict
first: that appends a non-`accept` verdict, which flips the unit back to
**in-flight** and **re-arms its lease** on its pages. The next dogen-write pass then
re-drafts it. (Because the reopened unit again holds its lease, a competitor that
took one of its pages while it was sealed is now refused at that unit's next draft.)

**Superseding a sealed page (worked example):** declaring or editing onto a page a
*sealed* unit owns succeeds and records a supersede — this mirrors the tested
end-to-end scenario:

- *Before:* unit **A** covers `docs/guide.md` and its latest review is an **accept**,
  so A is **sealed** and has released its lease on the page.
- unit **B** declares onto `docs/guide.md`. Because A is sealed (not in-flight), the
  claim is allowed rather than refused.
- *After:* B's declare commit records the takeover — a body line
  `extends: docs/guide.md extends unit A (sealed <sha12>)` plus a `Dogen-Extends: A`
  trailer — and B then drafts and reviews as usual until **B seals `docs/guide.md`**.
  (Had A still been in-flight, B's declare would instead refuse with `target_claimed`.)

**The plan is stale (unit.md changed after signoff):** surface it in the provenance
summary; the reviewer may want the plan re-approved (`dogen signoff --re-sign`)
before judging a draft made under the old approval. When the review itself orders
a plan amendment (say, moving the page), prescribe the folded form —
`dogen unit edit <id> --target <new-path> --re-sign` — one act, no stale-plan
limbo.

**The page landed at the wrong path:** before concluding "a CLI bug wrote it
wrong", read the unit's stored target (`dogen unit show <id> --json` →
`sphinx_target` / `extra_targets`). If the stored target is itself wrong (e.g. it
carries a stray `docs/` the declare step should have stripped, or points at the
wrong slot), the fix is a plan amendment: prescribe the folded
`dogen unit edit <id> --target <correct-path> --re-sign`, then route to
dogen-write to re-draft at the corrected path. **Never** resolve a placement
finding by handing the TA a raw shell `mv` — that leaves the seal bound to the
wrong path and the plan pointing elsewhere (round 3's opencode leg). The move is
a recorded plan act, not a filesystem workaround.

**Empty or honest-empty provenance:** present it truthfully (e.g. "the writer
recorded reading nothing"); an empty `context_origins` against non-empty `sources`
is a review signal worth surfacing, not an error to hide. Recorded `gaps` are the
writer's own declared uncertainty — surface them; they often seed the next steering
note.
</edge_cases>

<constraints>
<must>
- Offer two selectable modes up front (record vs review) via `AskUserQuestion`, and
  present a human-readable provenance summary (signoff + plan freshness,
  provider/mode/model/origin, declared vs actually-read sources with commit stamps,
  recorded gaps, steering stream, progress state) in both modes before eliciting a
  verdict.
- In review mode, present the four-dimension findings (source-fidelity,
  completeness, structure-fit, clarity) grouped by dimension, each tagged must-fix /
  should-fix / nit per `references/review-rubric.md`, before the verdict — and
  ground source-fidelity/completeness findings by re-checking claims against the
  recorded sources, not just the draft text.
- Record the reviewer's verdict via the single delegating
  `dogen review <id> --verdict accept|fix|redraft --note "…"` call (advances
  progress to `reviewed`; fix/redraft notes land in the steering stream) —
  and record it BEFORE any re-draft is invoked.
- Route off the `--json` result's `next_id` token, translated into skill
  language per `../README.md`'s routing table; never parrot the raw CLI `next`
  line to the TA. Quote the transition commit (`commit` field / the
  `git: committed` line) in the closing summary.
- Restrict `Bash` to read-only inspection plus the one delegating `dogen review`
  call.
- Surface CLI `reason` codes (e.g. `not_drafted`, `already_accepted`) in plain
  language and route accordingly; use the shared status vocabulary from
  `../README.md`.
</must>
<must_not>
- D-13: Never run `sphinx-build` or any build — building and publishing are out of
  dogen's scope; the reviewer/merger owns them.
- D-14: Never publish, push, or run a git state-changing command — the CLI's commit
  seam owns the transition commit; the human owns publishing.
- Never edit the draft, `unit.md`, or any file — this skill has no `Write`/`Edit`
  tool — and never suggest that the reviewer or TA hand-edit the draft as the
  way to apply findings: the correction path is a recorded fix/redraft verdict
  plus a dogen-write pass, full stop.
- Do not dump the raw page source into the conversation by default; offer it only on
  the reviewer's request.
- D-03: Never re-coin the CLI run-status vocabulary — the failure reason codes and
  the progress states stay surfaced verbatim from `--json` for run-status, never
  renamed into skill words. The review-findings priority axis (must-fix / should-fix
  / nit) is a separate, orthogonal concept — a finding's urgency, not the CLI
  operation's outcome — and must never rename, parallel, or collide with those
  machine status words (the sanctioned D-03 revisit). The verdict words
  (accept / fix / redraft) are the CLI's own `--verdict` vocabulary, surfaced
  verbatim — never a third taxonomy.
</must_not>
</constraints>

<output_specification>
Present, inline in the conversation (no file is written).

**review mode** — the provenance summary, then the findings grouped by dimension,
then the verdict:

```
## dogen-review — findings: <unit-id>

### Provenance
- Signoff: <author> at <when> — plan <fresh | changed since signoff>
- Provider / mode / model / origin: <provider> / <mode> / <model> / <model_origin>
- Declared sources: <unit.md sources, with commit stamps>
- Actually read (context_origins): <records, with commit stamps>
- Writer-declared gaps: <gaps, or (none)>
- Steering stream: <N entries; latest quoted>
- Progress: <progress state>

### source-fidelity
- [must-fix] <observation, quoting the offending draft text> → <suggested action>
- [nit] <observation> → <action>

### completeness
- [should-fix] <observation> → <action>

### structure-fit
- (none)

### clarity
- [nit] <observation> → <action>

Findings: N total — X must-fix, Y should-fix, Z nit.
(Priority = review findings, NOT the CLI run-status codes.)

### Verdict
<accept | fix | redraft> — <the reviewer's note, recorded via `dogen review`>
Committed: <sha7 from the CLI's `git: committed` line>

Next: /dogen-write — apply the recorded fix.
      (the frozen referral line for this `next_id` + verdict; see
      ../README.md's routing table — never the raw CLI `next` string)
```

**record mode** — the provenance summary and the verdict only (the findings sections
are skipped).

The recorded artifact is the CLI-persisted structured review (advancing
`progress -> reviewed`); this presentation itself is never written to a file.
</output_specification>

<success_criteria>
- [ ] The review mode (record or review) was selected up front via `AskUserQuestion`.
- [ ] A human-readable provenance summary (signoff + plan freshness,
      provider/mode/model/origin, declared vs actually-read with commit stamps,
      gaps, steering stream, progress) was presented in the selected mode.
- [ ] In review mode, the four-dimension findings were presented grouped by
      dimension with must-fix/should-fix/nit tags, grounded by re-checking claims
      against the recorded sources; in record mode the findings were skipped.
- [ ] The raw page source was not dumped by default; it was offered only on request.
- [ ] The reviewer's verdict was recorded via `dogen review <id> --verdict --note`
      (progress -> reviewed) BEFORE any re-draft; no `sphinx-build` was run (D-13).
- [ ] No publish or git state-changing command was run, no file was edited by
      the skill, and hand-editing the draft was never suggested as the way to
      apply findings (D-14).
- [ ] The routing came from `next_id` translated into skill language (no raw
      CLI `next` line was parroted); a fix/redraft verdict was routed back to
      dogen-write with the note landed in the steering stream, and the review
      commit's hash was quoted.
</success_criteria>

<self_healing>
After completing a run, or after any error that required a workaround, check whether
the issue came from a gap or inaccuracy in this skill's instructions, references, or
workflow steps.

What qualifies for a skill update:

- Tooling issues (CLI syntax changes, path changes, deprecated commands)
- Structural problems (missing files, wrong folder layout, dangling references)
- Missing edge cases that caused failures
- Incorrect assumptions about the environment or dependencies

Off-limits for self-edits: the skill's objective, the workflow step sequence, and the
success criteria. Propose changes to those to the user as ideas, never as self-edits.

How to update:

1. Report to the user: (a) the gap detected, (b) which skill file needs the change,
   (c) the proposed change, quoted in full.
2. Wait for explicit confirmation.
3. Apply the change directly to the skill file with Edit (or Write for new reference
   files).
4. Preserve the shared skill conventions: section order, this self_healing block, and
   the <NAME> placeholder style.
</self_healing>
