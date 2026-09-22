---
name: dogen-write
description: Drafts a review-ready, Sphinx-publishable page (MyST or rST — the target extension decides) for a declared and signed-off documentation unit, branching on the unit's declared Diátaxis intent — reference and explanation are authored straight from the declared sources; tutorial and how-to are authored from an evidence-gated step walk (each step captured as proof and recorded via dogen-record-step.sh) and curated excerpts of what actually ran. Stages under .dogen/staging/ and records via dogen-record-draft.sh, which enforces the HITL gate and — for actionable units — refuses until every step is resolved. Carries Write for staging files only. Use when a TA is ready to draft a signed-off unit.
allowed-tools: Read, Bash, Glob, Grep, Write, Edit
---

<objective>
Draft a review-ready, Sphinx-publishable page for a unit that has already been
declared and signed off. The host agent (the one the TA is talking to) authors the
page itself — starting from the unit's declared sources and navigating the repo
freely — stages it under `.dogen/staging/`, then calls `dogen-record-draft.sh` to
record it. The script enforces the HITL gate (refuses without a valid signoff), the
WR-03 write ordering (ledger before page), the identical-redraft suppression
(no-ops on byte-identical re-drafts), and — for actionable units — the
all-steps-resolved gate (refuses while any step is `unverified`).

The skill branches on the unit's declared Diátaxis `intent`:

- **reference** and **explanation** are authored straight from the declared
  sources (explanation additionally from the recorded intent steering).
- **tutorial** and **how-to** are authored from an evidence-gated step walk: the
  agent proposes one annotated step plan, walks it silent-until-signal capturing
  verbatim proof (bytes + exit code + SHA-256) recorded through
  `dogen-record-step.sh`, then authors the page from curated, env-scrubbed
  excerpts of what actually ran.

The unit's format is decided by its target extension: `.md` → MyST, `.rst` →
reStructuredText. Author in that markup, matching the page's siblings.
</objective>

<Iron-Law>
NO DRAFT RECORDED WITHOUT A VALID SIGNOFF. `dogen-record-draft.sh` enforces this
— it will exit 1 if the gate fails. Do NOT attempt to write the page directly to
`docs/` bypassing the script. The script writes the ledger row BEFORE the page
(WR-03); bypassing it means no audit trail for the draft.
</Iron-Law>

<Iron-Law>
NO ACTIONABLE DRAFT WITHOUT RESOLVED STEPS. For a tutorial or how-to, every step
must be `resolved` in the ledger's `## steps` section before recording —
`dogen-record-draft.sh` enforces this (exit 4 if any step is `unverified`). Never
skip the walk for an actionable unit.
</Iron-Law>

<quick_start>
1. Confirm the target unit id. Read `.dogen/units/<id>/unit.md` for the plan
   (intent, audience, title, sources, target, format) and `.dogen/units/<id>/ledger.md`
   for the signoff and any steering notes.
2. Branch on `intent`. **Author-straight** (reference / explanation): ground from
   the declared sources and author directly. **Evidence-walk** (tutorial / how-to):
   propose one annotated step plan, walk it silent-until-signal capturing verbatim
   proof, and record each step via `dogen-record-step.sh` before authoring.
3. Author the page in the unit's format (MyST for `.md`, rST for `.rst`), loading
   the direction register for the declared intent.
4. Stage the draft under `.dogen/staging/<id>/draft.<ext>`.
5. Call `dogen-record-draft.sh <id> <staged-draft> --model <model>` via `Bash`.
6. Report the recorded draft and route the TA to dogen-review.
</quick_start>

<pipeline>
dogen-fetch -> dogen-plan -> dogen-write -> dogen-review

This skill is the sole drafting stage. It consumes a declared+signed-off unit and
produces a recorded draft (via `dogen-record-draft.sh`, advancing the ledger's
`## generations` section). It branches on the unit's declared `intent`: reference
and explanation author straight from sources; tutorial and how-to first walk an
evidence-gated step plan. On success it hands off to dogen-review.
</pipeline>

<workflow>
<step_1 name="Read the unit state and steering">
Confirm the unit id, then read the full unit state:

- `.dogen/units/<id>/unit.md` — the plan: intent, audience, title, sources (with
  commit stamps), `sphinx_target` (where the page lands), and the format
  (`.md` → MyST, `.rst` → rST).
- `.dogen/units/<id>/ledger.md` — the `## signoff` section (verify it exists),
  the `## steering` section (every entry is guidance a re-draft MUST honour), the
  `## generations` section (if non-empty, this is a re-draft — the correction
  must be in the steering stream), and the `## steps` section (for an actionable
  unit, an existing step plan).

**Re-draft precondition:** if `## generations` is non-empty, the correction that
motivates this re-draft must already be RECORDED — a `fix`/`redraft` review verdict
or a steering note newer than the last generation. If the steering stream holds
nothing new, STOP and route back: the reviewer records the verdict first
(dogen-review), or the TA appends a steering note to the ledger.

Then branch on the unit's declared intent (from unit.md frontmatter):

- reference   → steps 2–6 (ground from sources; author the reference register; record)
- explanation → steps 2–6 (ground from sources + recorded intent; author the explanation register; record)
- tutorial    → step 1a (propose a step plan, walk it under the evidence gate) before steps 2–6, authoring in the tutorial register
- how-to      → step 1a, before steps 2–6, authoring in the how-to register
</step_1>

<step_1a name="Walk the actionable unit (tutorial / how-to only)">
Load `references/walk-protocol.md` now for the evidence contract, capture
mechanics, consent, workspace, and resume detail.

**Resume:** when a step plan exists and some steps are `unverified`, offer resume
as the default. Show the step-status table from the ledger, trust every `resolved`
step's evidence, and continue the walk at the first `unverified` step. The
workspace under `.dogen/staging/<id>/scratch/` persists across sessions.

**Investigate and propose ONE annotated plan.** Read the unit's declared `sources`
and navigate the repo freely to understand what the tutorial/how-to must walk.
Then propose **ONE annotated step plan**, presenting numbered steps
conversationally. For each step surface, inline:

- its **execution mode** — agent-runs (the default) or TA-runs;
- a **destructive/stateful marker** when the step's command would mutate real state;
- key **assumptions** and **invariants**.

The TA edits the plan conversationally — add, drop, reorder, re-word — until
satisfied. Then take **one confirmation** and persist the whole plan to the ledger.

Write the step plan to the `## steps` section of `ledger.md` with `Edit`. Each
step row has this format; separate consecutive step rows (and the section header
from the first row) with a single blank line:

```
## steps
step-1 | text_hash: <sha256 of step text> | status: unverified

step-2 | text_hash: <sha256 of step text> | status: unverified
```

The `text_hash` is the SHA-256 of the step's text — `dogen-record-step.sh` uses it
for staleness detection (if the step text changes after evidence is captured, the
evidence is stale).

Commit the step plan with the Dogen trailers (stages only `.dogen/`, never the
whole repo):

```bash
git add .dogen/ && git commit -q -m "dogen: step-plan ${UNIT_ID}" \
  --trailer "Dogen-Unit: ${UNIT_ID}" --trailer "Dogen-Phase: step-plan"
```

**Walk each step (silent-until-signal).** Load `references/episode-taxonomy.md`
now for the improvisation-vs-frustration taxonomy. Walk the plan one step at a
time with a **silent-until-signal** cadence: emit one status line per step.
Consult the TA only at:

- a **genuine fork** — missing information, or an informed choice with doc-visible
  consequences;
- a **destructive/stateful permission gate** — just-in-time, right before a marked
  step runs;
- a **failed step**.

**Agent-runs (default):** run the command cwd-pinned inside the workspace,
capturing full bytes with `tee`, a SHA-256 with `sha256sum`, and a real exit code:

```bash
WS=".dogen/staging/$UNIT_ID/scratch"; mkdir -p "$WS/evidence"
( cd "$WS" && <cmd> ) 2>&1 | tee "$WS/evidence/<step>.out"; echo "exit:${PIPESTATUS[0]}"
SHA=$(sha256sum "$WS/evidence/<step>.out" | cut -d' ' -f1)
```

**TA-runs:** print the exact copy-pasteable command with capture built in and let
the TA run it, then ingest the resulting file unmodified.

**Improvisation:** when the planned step did not say *how* and you had to figure it
out, record the step as a `deviated` verdict (exit 0) with a `reason`. It still
resolves so the walk proceeds.

**Recording a step's evidence:** write the evidence to a temp file, then call:

```bash
dogen-record-step.sh "$UNIT_ID" "<step-id>" --evidence-file "<evidence-file>"
```

The evidence file is a simple `key: value` format:

```
exit_code: 0
output_sha256: <sha256 of the captured output>
verdict: pass
mode: agent
command: <the command that ran>
step_text_sha256: <sha256 of the step text from the plan>
```

The script:
1. Validates required fields (pass/fail needs `output_sha256` + `exit_code`).
2. Checks staleness (`step_text_sha256` must match the `text_hash` in the ledger).
3. Updates the step row to `status: resolved` with the evidence fields.
4. Commits with `Dogen-Phase: step` / `Dogen-Step: <step-id>` trailers.

**On exit 1 (evidence incomplete):** re-capture with well-shaped proof. Never fabricate.
**On exit 3 (stale evidence):** the step text changed since capture. Re-capture or
update the step's `text_hash` in the ledger.
**On exit 0:** the step is resolved. Continue to the next step.

Recording a `fail` **succeeds** (its status stays `unverified`); it is the draft
macro-gate (in `dogen-record-draft.sh`, exit 4) that blocks on unresolved steps.
Before proceeding to step 2, verify every step is `resolved` by grepping the
`## steps` section for `status: unverified` — there should be zero hits.
</step_1a>

<step_2 name="Ground the draft">
Start from the unit's declared `sources` — read them in full; they are the primary
grounding. Then navigate the repo freely wherever a fact's origin lies: implementations,
fixtures, sibling docs, `.dogen/context/` artifacts, and — if present — a top-level
`optional-guidance/` directory. The declared sources are starting points, not a
boundary.

For an actionable unit, the grounding is the walk itself: the captured step
evidence (bytes + exit code + SHA-256) is the primary source, and the page is
authored from curated excerpts of what actually ran.

Ground every behavioral claim with the three-check rule: locate, confirm, corroborate.
Never assert what you have not read. Keep a running list of every file you read —
it becomes the context report.
</step_2>

<step_3 name="Author the page">
Load `references/writing-standards.md` now for the editorial standard. Then load
the direction register matching the unit's declared `intent`:

- reference   → `references/reference-stance.md`
- explanation → `references/explanation-stance.md`
- tutorial    → `references/tutorial-stance.md`
- how-to      → `references/how-to-stance.md`

Author a Sphinx-publishable page in the unit's Diátaxis direction, following the
loaded register. Reference code entities by qualified name; show a code block only
when the reader themselves authors or invokes it. Facts you cannot verify at their
origin are left out of the prose and recorded as gaps — never hedged into the page.
For an actionable unit, captured step output enters the page only as curated,
env-scrubbed excerpts — never a raw capture.

**Coverage check (before staging):** walk the unit plan's `## Outline / acceptance`
items one by one against the authored page. Every item is either present or recorded
as a gap with a reason — never silently dropped.

**Stance check:** grep the authored page for the banned researcher register, for
implementation identifiers (type/function names, `internal/` paths), and for
runtime-mechanics narration. Fix every hit before staging.
</step_3>

<step_4 name="Stage the draft and context report">
Write the authored page to `.dogen/staging/<id>/draft.<ext>` (where `<ext>` matches
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
dogen-record-draft.sh "$UNIT_ID" \
  ".dogen/staging/$UNIT_ID/draft.$EXT" \
  --model "$MODEL"
```

The script:
1. Checks the gate (signoff exists + plan hash matches) — exits 1 if it fails.
2. For an actionable unit, checks every step is `resolved` — exits 4 if any is
   `unverified`.
3. Compares the draft SHA-256 to the last generation — exits 3 if identical (no-op).
4. Writes the generation row to `ledger.md` (WR-03: ledger BEFORE page).
5. Copies the draft to `docs/<target>`.
6. Commits with `Dogen-Unit:` / `Dogen-Phase: draft` / `Dogen-Draft:` trailers.

**On exit 1 (gate refusal):** route the TA back to dogen-plan to sign off (or
re-sign if the plan changed).
**On exit 4 (unresolved steps):** an actionable unit still has `unverified` steps.
Return to step 1a and finish the walk before recording.
**On exit 3 (identical redraft):** the draft is byte-identical to the last pass —
nothing was recorded. Surface this to the TA.
**On exit 0:** the draft is recorded. Quote the `git: committed <sha7>` line and
route to dogen-review.
</step_5>

<step_6 name="Report and route">
Report the recorded draft:

```
## dogen-write: <unit-id>

- Draft: .dogen/staging/<unit-id>/draft.<ext>
- Recorded draft: docs/<target>
- Committed: <sha7 from the script's git: committed line>
- Progress: drafted

Next: /dogen-review — review the draft.
```

For an actionable unit, also surface the walk's quality signals (deviation / skip
/ fail counts from the ledger's `## steps` section).

Do not commit, stage, push, or build — the script's commit seam already recorded
the transition.
</step_6>
</workflow>

<edge_cases>
**Gate refusal (exit 1 — no signoff or stale plan):** route the TA back to dogen-plan.
If the plan changed after signoff, the TA needs to re-sign: edit `unit.md`, then
`dogen-signoff.sh <id> --force`.

**Unresolved steps (exit 4 — actionable unit):** a tutorial or how-to still has
`unverified` steps. Return to step 1a and finish the walk before recording. Never
skip the walk for an actionable unit.

**Identical redraft (exit 3):** the draft is byte-identical to the last generation.
Nothing was recorded. Surface this — the TA may want to apply steering before re-drafting.

**Re-draft with no recorded steering:** if `## generations` is non-empty but the
`## steering` section has nothing newer than the last generation, STOP. The correction
must be recorded first (a review verdict or a steering note) — never apply corrections
carried only in conversation.

**Evidence incomplete (exit 1 from dogen-record-step.sh):** the micro-gate refused
ill-shaped proof. Re-capture with well-shaped mechanical proof (bytes + exit code +
SHA-256). Never fabricate.

**Stale evidence (exit 3 from dogen-record-step.sh):** the step text changed since
the evidence was captured. Either re-capture the evidence against the current step
text, or update the step's `text_hash` in the ledger to match.

**A destructive-smelling command with no marker:** re-prompt for just-in-time consent
or switch the step to TA-runs.

**A fact you cannot verify:** leave it out of the prose and record it under gaps in
the report — a gap is provenance, not content.

**Honest framing:** the gate proves a well-shaped capture exists, not that it was not
forged. Never present the evidence as tamper-proof.
</edge_cases>

<constraints>
<must>
- Read the unit state first (`unit.md` + `ledger.md`) and honour every steering entry.
- Branch on the declared `intent` before drafting; never author an actionable unit
  without walking it.
- On a re-draft, require the correction to be RECORDED before drafting.
- Ground every behavioral claim with the three-check rule (locate, confirm, corroborate).
- For an actionable unit, propose ONE annotated step plan, walk silent-until-signal,
  capture agent-runs steps mechanically, and record via `dogen-record-step.sh`.
- Verify all steps are `resolved` before recording an actionable draft.
- Write ONLY the staging files (draft + report) under `.dogen/staging/<id>/`.
- Record every draft through `dogen-record-draft.sh`, which owns the gate, WR-03
  ordering, the all-steps-resolved gate, and the commit seam.
- Author in the unit's format: MyST for `.md`, rST for `.rst`.
</must>
<must_not>
- Never write the canonical draft directly to `docs/` — the script owns that write.
- Never bypass the gate by writing the page without calling the script.
- Never commit, stage, push, or build — the script's seam owns the commit.
- Never assert a fact you have not read at its origin.
- Never narrate your evidence in the drafted prose ("observed", "the fixtures show").
- Never mark a step resolved without calling `dogen-record-step.sh`.
- Never accept a paraphrased narration as evidence — only mechanical capture records a step.
- Never paste raw captures (SHA-256 digests, exit-code lines, scratch paths) into the
  drafted page — curated, env-scrubbed excerpts only.
- Never run agent-runs commands in the real repo cwd; they are cwd-pinned to the
  throwaway workspace.
- Never claim the evidence gate is tamper-proof.
</must_not>
</constraints>

<success_criteria>
- [ ] The unit state was read first and every steering entry honoured.
- [ ] The draft branched on the declared `intent`; an actionable unit was walked
      before authoring.
- [ ] On a re-draft, the recorded steering stream held the correction BEFORE the pass.
- [ ] The draft was grounded in the declared sources with free navigation beyond them
      (or in the captured step evidence, for an actionable unit).
- [ ] For an actionable unit, ONE annotated step plan was proposed, edited
      conversationally, persisted with ONE confirmation, and every step was
      `resolved` via `dogen-record-step.sh` before recording.
- [ ] The page was authored in the unit's format with no researcher register or
      implementation identifiers in the prose.
- [ ] The draft was staged under `.dogen/staging/<id>/` and recorded via
      `dogen-record-draft.sh` (not written directly to `docs/`).
- [ ] The script exited 0 and the `git: committed <sha7>` line was quoted.
- [ ] The TA was routed to dogen-review.
</success_criteria>
