---
name: dogen-write
description: Drafts a review-ready, Sphinx-publishable reference or explanation page (MyST or rST — the unit's target extension decides) for a declared and signed-off documentation unit. The host agent authors the page itself, starting from the unit's declared sources and navigating the repo freely, stages it under .dogen/staging/, then calls dogen-record-draft.sh to record it (WR-03: ledger before page). Carries Write for staging files only. Use when a TA is ready to draft a signed-off unit.
allowed-tools: Read, Bash, Glob, Grep, Write
---

<objective>
Draft a review-ready, Sphinx-publishable **reference or explanation** page for a
unit that has already been declared and signed off. The host agent (the one the TA
is talking to) authors the page itself — starting from the unit's declared sources
and navigating the repo freely — stages it under `.dogen/staging/`, then calls
`dogen-record-draft.sh` to record it. The script enforces the HITL gate (refuses
without a valid signoff), the WR-03 write ordering (ledger before page), and the
identical-redraft suppression (no-ops on byte-identical re-drafts).

The unit's format is decided by its target extension: `.md` → MyST, `.rst` →
reStructuredText. Author in that markup, matching the page's siblings.
</objective>

<Iron-Law>
NO DRAFT RECORDED WITHOUT A VALID SIGNOFF. `dogen-record-draft.sh` enforces this
— it will exit 1 if the gate fails. Do NOT attempt to write the page directly to
`docs/` bypassing the script. The script writes the ledger row BEFORE the page
(WR-03); bypassing it means no audit trail for the draft.
</Iron-Law>

<quick_start>
1. Confirm the target unit id. Read `.dogen/units/<id>/unit.md` for the plan
   (intent, audience, title, sources, target, format) and `.dogen/units/<id>/ledger.md`
   for the signoff and any steering notes.
2. Ground the draft: read the declared sources in full, navigate the repo freely,
   read `.dogen/context/` artifacts.
3. Author the page in the unit's format (MyST for `.md`, rST for `.rst`).
4. Stage the draft under `.dogen/staging/<id>/handoff.<ext>`.
5. Call `scripts/dogen-record-draft.sh <id> <staged-draft> --model <model>` via `Bash`.
6. Report the recorded draft and route the TA to dogen-review.
</quick_start>

<pipeline>
dogen-plan -> dogen-write -> dogen-review

This skill is the drafting stage. It consumes a declared+signed-off unit and
produces a recorded draft (via `dogen-record-draft.sh`, advancing the ledger's
`## generations` section). On success it hands off to dogen-review.
</pipeline>

<workflow>
<step_1 name="Read the unit state and steering">
Confirm the unit id, then read the full unit state:

- `.dogen/units/<id>/unit.md` — the plan: intent, audience, title, sources (with
  commit stamps), `sphinx_target` (where the page lands), and the format
  (`.md` → MyST, `.rst` → rST).
- `.dogen/units/<id>/ledger.md` — the `## signoff` section (verify it exists),
  the `## steering` section (every entry is guidance a re-draft MUST honour), and
  the `## generations` section (if non-empty, this is a re-draft — the correction
  must be in the steering stream).

**Re-draft precondition:** if `## generations` is non-empty, the correction that
motivates this re-draft must already be RECORDED — a `fix`/`redraft` review verdict
or a steering note newer than the last generation. If the steering stream holds
nothing new, STOP and route back: the reviewer records the verdict first
(dogen-review), or the TA appends a steering note to the ledger.
</step_1>

<step_2 name="Ground the draft">
Start from the unit's declared `sources` — read them in full; they are the primary
grounding. Then navigate the repo freely wherever a fact's origin lies: implementations,
fixtures, sibling docs, `.dogen/context/` artifacts, and — if present — a top-level
`optional-guidance/` directory. The declared sources are starting points, not a
boundary.

Ground every behavioral claim with the three-check rule: locate, confirm, corroborate.
Never assert what you have not read. Keep a running list of every file you read —
it becomes the context report.
</step_2>

<step_3 name="Author the page">
Load `references/writing-standards.md` now for the editorial standard. For an
explanation unit, additionally load `references/explanation-stance.md`.

Author a Sphinx-publishable page in the unit's Diátaxis direction:

- **reference** → neutral, information-oriented register. Write as the product's
  reference, never as a researcher describing evidence. Banned register: "observed",
  "the corpus", "the fixtures show". Unverifiable facts become report gaps, never
  hedged prose.
- **explanation** → understanding-oriented prose (rationale, context, trade-offs,
  connections) from the recorded intent steering as its primary source, curated
  never pasted.

Reference code entities by qualified name; show a code block only when the reader
themselves authors or invokes it. Facts you cannot verify at their origin are left
out of the prose and recorded as gaps — never hedged into the page.

**Coverage check (before staging):** walk the unit plan's `## Outline / acceptance`
items one by one against the authored page. Every item is either present or recorded
as a gap with a reason — never silently dropped.

**Stance check:** grep the authored page for the banned researcher register, for
implementation identifiers (type/function names, `internal/` paths), and for
runtime-mechanics narration. Fix every hit before staging.
</step_3>

<step_4 name="Stage the draft and context report">
Write the authored page to `.dogen/staging/<id>/handoff.<ext>` (where `<ext>` matches
the target extension).

Write a context report to `.dogen/staging/<id>/report.md` listing:
- every file read (with its commit stamp or honestly empty),
- any confidence gaps (an empty gaps list needs a one-line justification).

These staging files are the ONLY files this skill writes. Never write directly to
`docs/` — the script owns that write.
</step_4>

<step_5 name="Record the draft via the script">
Call the deterministic script:

```bash
scripts/dogen-record-draft.sh "$UNIT_ID" \
  ".dogen/staging/$UNIT_ID/handoff.$EXT" \
  --model "$MODEL"
```

The script:
1. Checks the gate (signoff exists + plan hash matches) — exits 1 if it fails.
2. Compares the draft SHA-256 to the last generation — exits 3 if identical (no-op).
3. Writes the generation row to `ledger.md` (WR-03: ledger BEFORE page).
4. Copies the draft to `docs/<target>`.
5. Commits with `Dogen-Unit:` / `Dogen-Phase: draft` / `Dogen-Draft:` trailers.

**On exit 1 (gate refusal):** route the TA back to dogen-plan to sign off (or
re-sign if the plan changed).
**On exit 3 (identical redraft):** the draft is byte-identical to the last pass —
nothing was recorded. Surface this to the TA.
**On exit 0:** the draft is recorded. Quote the `git: committed <sha7>` line and
route to dogen-review.
</step_5>

<step_6 name="Report and route">
Report the recorded draft:

```
## dogen-write: <unit-id>

- Handoff: .dogen/staging/<unit-id>/handoff.<ext>
- Recorded draft: docs/<target>
- Committed: <sha7 from the script's git: committed line>
- Progress: drafted

Next: /dogen-review — review the draft.
```

Do not commit, stage, push, or build — the script's commit seam already recorded
the transition.
</step_6>
</workflow>

<edge_cases>
**Gate refusal (exit 1 — no signoff or stale plan):** route the TA back to dogen-plan.
If the plan changed after signoff, the TA needs to re-sign: edit `unit.md`, then
`dogen-signoff.sh <id> --force`.

**Identical redraft (exit 3):** the draft is byte-identical to the last generation.
Nothing was recorded. Surface this — the TA may want to apply steering before re-drafting.

**Re-draft with no recorded steering:** if `## generations` is non-empty but the
`## steering` section has nothing newer than the last generation, STOP. The correction
must be recorded first (a review verdict or a steering note) — never apply corrections
carried only in conversation.

**A fact you cannot verify:** leave it out of the prose and record it under gaps in
the report — a gap is provenance, not content.
</edge_cases>

<constraints>
<must>
- Read the unit state first (`unit.md` + `ledger.md`) and honour every steering entry.
- On a re-draft, require the correction to be RECORDED before drafting.
- Ground every behavioral claim with the three-check rule (locate, confirm, corroborate).
- Write ONLY the staging files (handoff + report) under `.dogen/staging/<id>/`.
- Record every draft through `dogen-record-draft.sh`, which owns the gate, WR-03
  ordering, and the commit seam.
- Author in the unit's format: MyST for `.md`, rST for `.rst`.
</must>
<must_not>
- Never write the canonical draft directly to `docs/` — the script owns that write.
- Never bypass the gate by writing the page without calling the script.
- Never commit, stage, push, or build — the script's seam owns the commit.
- Never assert a fact you have not read at its origin.
- Never narrate your evidence in the drafted prose ("observed", "the fixtures show").
</must_not>
</constraints>

<success_criteria>
- [ ] The unit state was read first and every steering entry honoured.
- [ ] On a re-draft, the recorded steering stream held the correction BEFORE the pass.
- [ ] The draft was grounded in the declared sources with free navigation beyond them.
- [ ] The page was authored in the unit's format with no researcher register or
      implementation identifiers in the prose.
- [ ] The draft was staged under `.dogen/staging/<id>/` and recorded via
      `dogen-record-draft.sh` (not written directly to `docs/`).
- [ ] The script exited 0 and the `git: committed <sha7>` line was quoted.
- [ ] The TA was routed to dogen-review.
</success_criteria>
