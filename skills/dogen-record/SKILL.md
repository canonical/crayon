---
name: dogen-record
description: Walks a Technical Author through an interactive, evidence-gated step plan and drafts a Sphinx-publishable tutorial or how-to from what actually ran. Proposes one editable numbered plan, walks each step silent-until-signal while capturing verbatim proof (redirected bytes, a real exit code, a SHA-256) recorded through dogen-record-step.sh, and finally authors page(s) it stages and records via dogen-record-draft.sh. Carries Write for staging files only. Use when a TA has a declared and signed-off actionable unit (tutorial or how-to) whose content must be produced by doing, not extracted from artefacts.
allowed-tools: Read, Bash, Glob, Grep, Write, Edit, AskUserQuestion
---

<objective>
Produce a review-ready, Sphinx-publishable **tutorial or how-to** page for a
declared and signed-off documentation unit by walking the TA through an interactive,
evidence-gated step plan and drafting from what actually ran. This is the action-based
counterpart to dogen-write: content that cannot be extracted from artefacts alone is
produced by *doing* — propose one editable numbered plan, walk each step capturing
verbatim mechanical proof, then author the page from curated excerpts of that proof.

The skill carries **judgment**; the deterministic script `dogen-record-step.sh`
holds the **provable evidence gate** (refuses a step marked done without a
well-shaped mechanical capture — SHA-256 + exit code + staleness check). All
persistence flows through `dogen-record-step.sh` and `dogen-record-draft.sh`.

Ceremony is calibrated below the circumvention threshold: one annotated plan, one
confirmation, then silent-until-signal — never a confirm-every-step parade.
</objective>

<Iron-Law>
NO STEP RESOLVED WITHOUT MECHANICAL PROOF. `dogen-record-step.sh` enforces this —
it will exit 1 if the evidence is incomplete (no `output_sha256` or `exit_code` for
a pass/fail), and exit 3 if the evidence is stale (the step text changed since
capture). Do NOT mark a step resolved in the ledger without calling the script.
</Iron-Law>

<quick_start>
1. Confirm the target unit. Read `unit.md` and `ledger.md` for the plan and signoff.
2. Precondition: the unit must be declared and signed off. If not, route to dogen-plan.
3. Investigate the declared sources and the repo, then propose ONE annotated step plan.
4. Walk each step silent-until-signal, capturing verbatim proof (bytes + exit code + SHA-256).
5. Record each step's evidence via `dogen-record-step.sh`.
6. Author the page(s) from curated, env-scrubbed excerpts, stage, and record via
   `dogen-record-draft.sh`. Route to dogen-review.
</quick_start>

<pipeline>
(dogen-plan) -> dogen-record -> dogen-review

This skill is the action-based drafting stage — the alternative to dogen-write for
tutorial/how-to units. It consumes a declared+signed-off unit, walks an evidence-gated
step plan, and produces a recorded draft. On success it hands off to dogen-review.
</pipeline>

<workflow>
<step_1 name="Open or resume">
Confirm the unit id. Read:

- `.dogen/units/<id>/unit.md` — the plan: intent, audience, title, sources, target, format.
- `.dogen/units/<id>/ledger.md` — check for a `## steps` section (existing plan)
  and the signoff.

**Resume:** when a step plan exists and some steps are `unverified`, offer resume as
the default. Show the step-status table from the ledger, trust every `resolved` step's
evidence, and continue the walk at the first `unverified` step. The workspace under
`.dogen/staging/<id>/scratch/` persists across sessions.

**Precondition:** the unit must be declared and signed off (the `## signoff` section
must exist in the ledger). If it doesn't, route the TA to dogen-plan to declare and
sign off first. Never bypass the HITL gate.
</step_1>

<step_2 name="Investigate sources and propose one annotated plan">
Read the unit's declared `sources` and navigate the repo freely to understand what
the tutorial/how-to must walk. Then propose **ONE annotated step plan**:

Present numbered steps conversationally. For each step surface, inline:
- its **execution mode** — agent-runs (the default) or TA-runs;
- a **destructive/stateful marker** when the step's command would mutate real state;
- key **assumptions** and **invariants**.

The TA edits the plan conversationally — add, drop, reorder, re-word — until satisfied.
Then take **one confirmation** and persist the whole plan to the ledger.

Write the step plan to the `## steps` section of `ledger.md` with `Edit`. Each step
row has this format:

```
step-1 | text_hash: <sha256 of step text> | status: unverified
step-2 | text_hash: <sha256 of step text> | status: unverified
```

The `text_hash` is the SHA-256 of the step's text — `dogen-record-step.sh` uses it
for staleness detection (if the step text changes after evidence is captured, the
evidence is stale).

Commit the step plan using the shared commit helper (stages only `.dogen/` and
`docs/`, never the whole repo):

```bash
source scripts/dogen-common.sh
git add .dogen/ && git commit -q -m "dogen: step-plan ${UNIT_ID}" \
  --trailer "Dogen-Unit: ${UNIT_ID}" --trailer "Dogen-Phase: step-plan"
```
</step_2>

<step_3 name="Walk each step (silent-until-signal)">
Walk the plan one step at a time with a **silent-until-signal** cadence: emit one
status line per step. Consult the TA only at:
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
scripts/dogen-record-step.sh "$UNIT_ID" "<step-id>" --evidence-file "<evidence-file>"
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
macro-gate (in `dogen-record-draft.sh`) that blocks on unresolved steps — but
`dogen-record-draft.sh` doesn't check steps. The skill must verify all steps are
resolved before drafting.
</step_3>

<step_4 name="Draft handoff (mirror dogen-write's passenger flow)">
Once every step is `resolved` (verify by grepping the `## steps` section for
`status: unverified` — there should be zero hits), author the page(s).

1. **Author** a Sphinx-publishable tutorial or how-to in the unit's format (MyST for
   `.md`, rST for `.rst`). Captured step output enters the page only as **curated,
   env-scrubbed excerpts** — deliberately selected and scrubbed of paths, timestamps,
   hostnames, SHA-256 digests, exit-code lines, and scratch-workspace paths. Provenance
   keeps the verbatim truth; the page gets the reader-facing version. Never paste a
   raw capture.

2. **Stage** the handoff: `.dogen/staging/<id>/handoff.<ext>` (single page) or
   `.dogen/staging/<id>/handoff/` (multi-file).

3. **Write** the context report to `.dogen/staging/<id>/report.md` — every file read
   (commit-stamped), tools used, and honest gaps.

4. **Record** through the deterministic script:

```bash
scripts/dogen-record-draft.sh "$UNIT_ID" \
  ".dogen/staging/$UNIT_ID/handoff.$EXT" \
  --model "$MODEL"
```

The script enforces the HITL gate (signoff exists + plan hash matches), writes the
generation row to the ledger (WR-03: ledger before page), copies the draft to
`docs/<target>`, and commits.
</step_4>

<step_5 name="Report and route">
Report the recorded draft and quote the `git: committed <sha7>` line. Surface the
walk's quality signals (deviation / skip / fail counts). Route the TA to dogen-review.

```
## dogen-record: <unit-id>

- Steps: <N total — R resolved, U unverified>
- Quality signals: <D deviated, S skipped, F failed>
- Recorded draft: docs/<target>
- Committed: <sha7>

Next: /dogen-review — review the draft.
```
</step_5>
</workflow>

<edge_cases>
**Unit not signed off:** route the TA to dogen-plan. Never bypass the HITL gate.

**Evidence incomplete (exit 1):** the micro-gate refused ill-shaped proof. Re-capture
with well-shaped mechanical proof (bytes + exit code + SHA-256). Never fabricate.

**Stale evidence (exit 3):** the step text changed since the evidence was captured.
Either re-capture the evidence against the current step text, or update the step's
`text_hash` in the ledger to match.

**A destructive-smelling command with no marker:** re-prompt for just-in-time consent
or switch the step to TA-runs.

**Honest framing:** the gate proves a well-shaped capture exists, not that it was not
forged. Never present the evidence as tamper-proof.
</edge_cases>

<constraints>
<must>
- Require a declared + signed-off unit before walking; route to dogen-plan when not.
- Propose ONE annotated step plan that the TA edits conversationally; persist with
  ONE confirmation.
- Walk silent-until-signal: one status line per step; consult the TA only at a fork,
  a permission gate, or a failed step.
- Capture agent-runs steps mechanically (cwd-pinned bytes + SHA-256 + exit code) and
  record via `dogen-record-step.sh`.
- Ingest TA-runs evidence from the tee'd file unmodified; never re-type or paraphrase.
- Author the draft from curated, env-scrubbed excerpts only; stage and record via
  `dogen-record-draft.sh`.
- Verify all steps are `resolved` before drafting.
</must>
<must_not>
- Never use `Write` anywhere except the staging files under `.dogen/staging/<id>/`.
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
- [ ] The unit was declared and signed off before the walk ran.
- [ ] ONE annotated step plan was proposed, edited conversationally, and persisted
      with ONE confirmation.
- [ ] The walk ran silent-until-signal; the TA was consulted only at forks, gates,
      and failures.
- [ ] Agent-runs steps captured verbatim proof (bytes + SHA-256 + exit code) and
      recorded via `dogen-record-step.sh`; TA-runs steps ingested the tee'd file
      unmodified.
- [ ] All steps were `resolved` before drafting; the draft was authored from curated
      excerpts and recorded via `dogen-record-draft.sh`.
- [ ] The TA was routed to dogen-review.
</success_criteria>
