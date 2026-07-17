---
name: dogen-record
description: Walks a Technical Author through an interactive, evidence-gated step plan and drafts a Sphinx-publishable tutorial or how-to from what actually ran — proposing one editable numbered plan (execution mode, destructive markers, and key assumptions inline), then walking each step silent-until-signal while capturing verbatim proof (redirected bytes, a real exit code, a SHA-256) recorded through the shipped `dogen record plan|step` gate, and finally authoring page(s) it stages and records via `dogen draft --draft-file/--draft-dir --report` exactly as dogen-write's passenger does. It carries Write for staging files only. Use when a TA has a declared and signed-off actionable unit (tutorial or how-to) whose content must be produced by doing, not extracted from artefacts.
allowed-tools: Read, Bash, Glob, Grep, Write
---

<objective>
Produce a review-ready, Sphinx-publishable **tutorial or how-to** page for a
declared and signed-off documentation unit by walking the Technical Author (TA)
through an interactive, evidence-gated step plan and drafting from what actually
ran. This is the action-based counterpart to dogen-write: content that cannot be
extracted from artefacts alone is produced by *doing* — propose one editable
numbered plan, walk each step capturing verbatim mechanical proof, then author
the page from curated excerpts of that proof.

The skill carries **judgment**; the shipped Phase-12 core holds the **provable
evidence gate** (`dogen record step` refuses a step marked done without a
well-shaped mechanical capture — default-FAIL) and the **commit seam** (the CLI
commits every transition itself, never run git commands that change state). All
persistence flows through the `dogen record plan|step|show` and
`dogen draft --draft-file/--draft-dir --report` verbs; this skill never writes
provenance and never re-judges "done" in prose — it shells the verb and branches
on the stable `--json` `reason` codes. It mirrors dogen-write's passenger draft
flow (author → stage under `.dogen/staging/<id>/` → record) and is, alongside
dogen-write, one of the two draft-stage skills that may carry `Write` — and only
for the staging files.

Ceremony is calibrated below the circumvention threshold: **if it's easier to
circumvent than to use, it will be circumvented.** One annotated plan, one
confirmation, then silent-until-signal — never a confirm-every-step parade.

Honest framing throughout: the evidence gate proves a well-shaped capture exists,
**not** that it was not forged; workspace containment is a skill-level tripwire,
not a core-verified guarantee. See `../README.md` for the shared family contract,
glossary, and status vocabulary.
</objective>

<quick_start>
1. First confirm the target unit and check its current state: run
   `dogen record show "$UNIT" --json` and `dogen unit show "$UNIT" --json`. When a
   step plan with partial evidence already exists, offer **resume** as the default
   (D-13) — continue at the first `unverified` step, trust every `resolved` step's
   evidence, and leave the workspace intact. Otherwise start a fresh walk.
2. Precondition (D-09): the unit must already be **declared and signed off** (the
   same precondition as dogen-write). If it is not, route the TA to declare it
   directly — `dogen unit new … --target <path.md|.rst>` then `dogen signoff <id>`
   — and return here. This skill touches dogen-plan zero (Phase 14 wires routing).
3. Investigate the declared sources and the repo, then propose **ONE annotated
   step plan**: numbered steps, each with its execution mode (agent-runs / TA-runs),
   a destructive/stateful marker, and key assumptions/invariants inline. The TA
   edits it conversationally until satisfied; **one confirmation** persists it via
   `dogen record plan "$UNIT" --steps-file - --json` in a single step-planned commit
   (D-10).
4. Load `references/walk-protocol.md` now for the reason-code→branch map, the
   capture mechanics (tee + sha256sum + a real exit code), the just-in-time consent
   gate and destructive backstop, the workspace lifecycle, and resume detail.
5. Walk each step **silent-until-signal** (D-12): one status line per step;
   consult the TA only at a genuine fork, a destructive/stateful permission gate,
   or a failed step. Record each step's evidence via
   `dogen record step "$UNIT" <step> --evidence-file - --json`. Improvisation is
   recorded as a `deviated` verdict (exit 0) whose reason carries the episode color.
6. Load `references/authoring-stance.md` now, then author the page(s) from
   **curated, env-scrubbed excerpts** of the captured proof, stage them under
   `.dogen/staging/<id>/`, and record via `dogen draft --draft-file`/`--draft-dir`
   `--report`. Quote the CLI's `git: committed <sha7>` line and route the TA to
   dogen-review.
</quick_start>

<pipeline>
(dogen-plan) -> dogen-record -> dogen-review

This skill is the action-based drafting stage — the alternative to dogen-write for
tutorial/how-to units. It consumes a declared+signed-off unit, walks an
evidence-gated step plan, and produces a recorded draft (via `dogen draft`); the
CLI's commit seam records every transition (`step-planned`, `step-recorded`, the
draft transition). Routing rules:

- On success it hands off to dogen-review with the frozen referral line
  (`Next: /dogen-review — review the draft.`).
- If a step's evidence record refuses with `evidence_required`, re-capture with
  well-shaped proof; never fabricate. If `dogen draft` refuses with
  `evidence_incomplete`, route back into the walk at the unresolved step(s).
- If the unit is not signed off, route the TA to declare + sign it off (D-09) —
  this skill does not bypass the HITL gate.
- The provable evidence gate is the core's — this skill calls the CLI and branches
  on its reason codes; it never re-implements the gate.
- `Write` is used ONLY for the staging files under `.dogen/staging/<id>/` (the
  scratch workspace, the handoff page(s), and the context report).
- The CLI commits transitions itself; this skill never commits, stages, or pushes.
</pipeline>

<workflow>
<step_1 name="Open or resume">
Confirm the unit id, then run the SK-05 state check:

```bash
dogen record show "$UNIT_ID" --json    # {steps:[{id,text,status,verdict}], all_steps_verified}
dogen unit show "$UNIT_ID" --json      # declared? signed off? sources, target, format
```

`record show` returns each step's **derived** status (`resolved` / `unverified`)
and `all_steps_verified` — nothing is stored, the status is computed on read (the
Phase-12 hash-bind means an edited step auto-reverts to `unverified`).

**Resume (D-13):** when a step plan exists and some steps are `unverified`, offer
resume as the default. Show the derived step-status table, trust every `resolved`
step's evidence, and continue the walk at the first `unverified` step. The
workspace under `.dogen/staging/<id>/scratch/` persists across sessions (D-07), so
prior evidence and produced state are intact. No new verb, no flag — resume is
detection, not a mode. Load `references/walk-protocol.md` now.
</step_1>

<step_2 name="Precondition — declared and signed off">
The unit must be **declared and signed off** before any step runs (D-09, the same
precondition as dogen-write). If `dogen unit show` reports no signoff, do not walk:
route the TA to declare the unit directly and sign it off —

```bash
dogen unit new "$UNIT_ID" --title "…" --target <path.md|.rst> --notes "…"
dogen signoff "$UNIT_ID"
```

— then return here. The interim entry is the TA declaring the unit via the CLI;
Phase 14 wires dogen-plan routing for actionable units. This skill touches
dogen-plan zero.
</step_2>

<step_3 name="Investigate sources and propose one annotated plan">
Read the unit's declared `sources` and navigate the repo freely to understand what
the tutorial/how-to must walk. Then propose **ONE annotated step plan** — the one
designed checkpoint (D-10, mirroring the shipped SK-03 batching precedent).

Present numbered steps conversationally. For each step surface, inline:

- its **execution mode** — agent-runs (the default) or TA-runs;
- a **destructive/stateful marker** when the step's command would mutate real
  state (agent-proposed, D-06 — the TA vetoes or corrects it like any other delta);
- key **assumptions** and **invariants** (`Step.assumptions` / `Step.invariants`).

The TA edits the plan conversationally — add, drop, reorder, re-word, re-mark,
flip a mode — until satisfied. Set the **upfront agent-runs-vs-TA-runs default**
here and honour any per-step override (REC-02). Then take **one confirmation** and
persist the whole plan:

```bash
printf '%s' "$STEPS_YAML" | dogen record plan "$UNIT_ID" --steps-file - --json
```

The steps-file is a YAML list of step mappings (`id`, `text`, `assumptions`,
`invariants`, `consumed`, `produced`, `deterministic`); the exact shape is in
`references/walk-protocol.md`. `record plan` whole-replaces the plan and keeps the
recorded evidence of any step whose text hash is unchanged (D-12) — so a mid-walk
re-plan at a fork is cheap and safe, re-verifying only the changed step. A
malformed file refuses with `bad_steps_file` before anything crosses into core.

**Seam-gap flag (REC-02):** the shipped `Step` schema carries **no persisted
planned-mode field** — mode lives on the evidence record (`StepEvidence.mode`)
only *after* a step runs. The upfront default and per-step overrides are therefore
**conversational**, re-proposed on resume. This is a stated planning-time flag,
not a silent core edit.

**Seam-gap flag (REC-06):** the `Step` schema carries **no persisted
destructive/stateful marker**. The marker is **conversational** (surfaced at plan
review); the D-06 runtime destructive backstop (step 4) is the safety net, so
safety never depends on persistence.
</step_3>

<step_4 name="Walk each step (silent-until-signal)">
Walk the plan one step at a time with a **silent-until-signal** cadence (D-12):
emit **one status line per step** (step id, verdict). Assumption/invariant deltas
surface only when something actually changed — one line the TA vetoes or ignores,
never a data-entry prompt. Actively consult the TA at exactly three signals:

- a **genuine fork** — missing information, or an informed choice with doc-visible
  consequences (REC-05). Every non-fork default is taken silently and logged as a
  delta.
- a **destructive/stateful permission gate** — just-in-time, right before a marked
  step runs (REC-06).
- a **failed step**.

**Agent-runs (default):** run the command **cwd-pinned** inside the workspace,
capturing full bytes with `tee`, a SHA-256 with `sha256sum`, and a real exit code:

```bash
WS=".dogen/staging/$UNIT_ID/scratch"; mkdir -p "$WS/evidence"
( cd "$WS" && <cmd> ) 2>&1 | tee "$WS/evidence/<step>.out"; echo "exit:${PIPESTATUS[0]}"
SHA=$(sha256sum "$WS/evidence/<step>.out" | cut -d' ' -f1)
```

Then record the step, with the command in **workspace-anchored** form (D-08) so
the transcript itself proves where it ran:

```bash
dogen record step "$UNIT_ID" <step> --evidence-file - --json
```

**TA-runs:** print the exact copy-pasteable command with capture built in (D-11)
and let the TA run it —

```bash
<cmd> 2>&1 | tee .dogen/staging/$UNIT_ID/scratch/evidence/<step>.out; echo exit:$?
```

— then ingest the resulting file **unmodified** into the evidence record. If the TA
pastes chat output instead, write the paste to the evidence file verbatim. Never
re-type, never paraphrase a narration as evidence.

**Destructive/stateful (D-06):** a marked step takes just-in-time consent right
before it runs, or the TA runs it themselves (TA-runs mode). An **unmarked**
command that smells destructive re-prompts via the runtime backstop instead of
running. Consent is confined to dangerous steps only — never a confirm-parade.

**Improvisation (REC-09 / D-14):** when the planned step did not say *how* and you
had to figure it out, record the step as a `deviated` verdict (exit 0) with a
`reason`. It still **resolves** (so the walk proceeds) and the reason rides the
`step-recorded` commit body as episode color — the walk replays from `git log`
alone. The improvisation-vs-frustration taxonomy is in
`references/episode-taxonomy.md`.

Recording a `fail` **succeeds** (its status stays `unverified`); it is the draft
macro-gate, not this record, that blocks on unresolved steps. Branch on the
`--json` `reason` codes (`evidence_required`, `bad_evidence_file`, `unknown_step`,
`unit_not_found`) per `references/walk-protocol.md` — never re-judge "done" in
prose.
</step_4>

<step_5 name="Draft handoff (mirror dogen-write's passenger flow)">
Once every step is `resolved` (`record show` reports `all_steps_verified: true`),
author the page(s). Load `references/authoring-stance.md` now — it governs the
tutorial-vs-how-to stance and the D-04 curated-excerpt rule.

1. **Author** a Sphinx-publishable tutorial or how-to in the unit's `format` (MyST
   for `.md`, reStructuredText for `.rst`). Captured step output enters the page
   only as **curated, env-scrubbed excerpts** (D-04) — deliberately selected and
   scrubbed of paths, timestamps, hostnames, sha256 digests, exit-code lines, and
   scratch-workspace paths. Provenance keeps the verbatim truth; the page gets the
   reader-facing version. Never paste a raw capture.
2. **Stage** the handoff exactly as dogen-write's passenger does: a single page at
   `.dogen/staging/<UNIT_ID>/handoff.<ext>`, or a `handoff/` tree mirroring a
   multi-file unit's target set. Move a mis-placed page — never delete a staged
   draft to fix layout.
3. **Write** the context report to `.dogen/staging/<UNIT_ID>/report.yaml` — every
   file read (commit-stamped), tools used, and honest gaps (an empty `gaps` list
   needs a one-line `gaps_note`). These staging files — the scratch workspace, the
   handoff, and the report — are the ONLY files this skill writes.
4. **Record** through the CLI:

```bash
# Single-page unit:
dogen draft "$UNIT_ID" \
  --draft-file ".dogen/staging/$UNIT_ID/handoff.$EXT" \
  --report ".dogen/staging/$UNIT_ID/report.yaml" \
  --provider host-harness --json
# Multi-file unit: --draft-dir ".dogen/staging/$UNIT_ID/handoff" instead of --draft-file
```

The draft **macro-gate refuses with `evidence_incomplete`** while any step is
unverified — route back into the walk at the unresolved step, resolve it, then
re-record. The HITL steering gate and provenance stay intact (the same passenger
flow dogen-write uses).
</step_5>

<step_6 name="Report and route">
Report the recorded draft from the `--json` output and quote the CLI's
`git: committed <sha7> — …` stderr line (the same hash arrives as `commit` in the
JSON) — the transition commit is the audit anchor; never assert the seam committed
it without the hash. Surface the walk's quality signals for the reviewer (deviation
/ skip / fail counts). Do not commit, stage, push, or build — the CLI's commit seam
already recorded the transition. On success, route the TA to dogen-review.
</step_6>
</workflow>

<edge_cases>
**Unit not signed off:** the walk's draft would refuse at the HITL gate. Route the
TA to declare + sign off the unit (D-09, step 2); do not bypass the gate.

**`evidence_required` on a step record:** the micro-gate refused ill-shaped proof
— a `pass`/`fail` with no hash or exit code, or a `skipped`/`deviated` with no
reason. Re-capture with well-shaped mechanical proof; never fabricate a hash or an
exit code.

**`evidence_incomplete` on draft:** the macro-gate refused because a step is
unverified. Return to the walk at the unresolved step, record its evidence, then
re-run the draft.

**`bad_steps_file` / `bad_evidence_file`:** the emitted YAML failed validation at
the compose root. Fix the file shape (see `references/walk-protocol.md`) and
re-emit — nothing crossed into core.

**`unknown_step`:** the step id is not in the recorded plan. Run `record plan`
first (or fix the id); the plan is the source of truth for step ids.

**A destructive-smelling command with no marker:** the runtime backstop re-prompts
instead of running it (D-06). Confirm with just-in-time consent or switch the step
to TA-runs; optionally re-plan to mark it.

**A one-shot green (network/time/random):** set `deterministic: false` on the step
so its green carries the single-sample asterisk, and surface it as an assumption —
authentic evidence is not the same as reproducible.

**Seam gaps (stated, not silently fixed):** there is no persisted planned-mode
field (REC-02) and no persisted destructive/stateful marker (REC-06). Both are
handled conversationally at plan review and re-proposed on resume; the D-06 runtime
backstop is the safety net for the marker. Neither is a core edit this phase.

**Honest framing:** the gate proves a well-shaped capture exists, not that it was
not forged; the cwd-pinned workspace (D-08) is a skill-level tripwire, not a
core-verified guarantee. Never present the evidence as tamper-proof.
</edge_cases>

<constraints>
<must>
- Confirm the target unit and check its current state first
  (`dogen record show --json` + `dogen unit show --json`); offer resume as the
  default when a partial step plan exists (D-13).
- Require a declared + signed-off unit before walking (D-09); route the TA to
  `dogen unit new` + `dogen signoff` when it is not, and never bypass the HITL gate.
- Propose ONE annotated step plan (execution mode, destructive markers, and
  assumptions/invariants inline) that the TA edits conversationally, and persist it
  with ONE confirmation via `dogen record plan --steps-file -` (D-10).
- Walk silent-until-signal (D-12): one status line per step; consult the TA only at
  a genuine fork, a destructive/stateful permission gate, or a failed step.
- Capture agent-runs steps mechanically — cwd-pinned in `.dogen/staging/<id>/scratch/`,
  full bytes via `tee`, a SHA-256 via `sha256sum`, and a real exit code — and record
  via `dogen record step --evidence-file -` with the command in workspace-anchored
  form (D-08).
- Ingest TA-runs evidence from the tee'd file (or pasted output) **unmodified**;
  never re-type or paraphrase a narration as evidence (REC-03).
- Take just-in-time consent (or TA-runs mode) before a destructive/stateful step
  runs, and let the runtime backstop re-prompt on an unmarked destructive-smelling
  command (D-06) — consent confined to dangerous steps only.
- Record improvisation as a `deviated` verdict (exit 0) whose reason carries the
  episode color into the commit body (REC-09 / D-14); use the taxonomy in
  `references/episode-taxonomy.md`.
- Author the draft from curated, env-scrubbed excerpts only (D-04); stage the
  handoff and context report under `.dogen/staging/<id>/`, then record via
  `dogen draft --draft-file`/`--draft-dir` `--report` — the passenger flow.
- Branch on the stable `--json` reason codes (`evidence_required`,
  `evidence_incomplete`, `bad_steps_file`, `bad_evidence_file`, `unknown_step`,
  `unit_not_found`) in plain language; surface them per `../README.md`.
- Quote the CLI's `git: committed <sha7>` line before asserting a transition
  committed; route the TA to dogen-review on success.
- State both seam-gap flags (no persisted planned-mode field; no persisted
  destructive marker) explicitly; keep honest framing (a well-shaped capture
  exists, not un-forged) throughout.
</must>
<must_not>
- Never use `Write` anywhere except the staging files under `.dogen/staging/<id>/`
  — the scratch workspace, the handoff page(s), and `report.yaml`.
- Never re-implement or re-judge the evidence gate in prose; the core enforces
  default-FAIL — this skill invokes `dogen record`/`dogen draft` and branches on
  reason codes.
- Never accept a paraphrased narration (a claim that a step worked) as evidence;
  only mechanical capture (bytes + exit code + sha256) records a step.
- Never store step state or add a `steps.yaml`/`evidence.yaml` sidecar; completion
  stays derived from provenance (EVID-03).
- Never paste raw captures (sha256 digests, exit-code lines, scratch-workspace
  paths, timestamps) into the drafted page — curated, env-scrubbed excerpts only
  (D-04).
- Never run agent-runs commands in the real repo cwd; they are cwd-pinned to the
  throwaway workspace (D-05/D-08). Only a stateful-marked step touches real state,
  via the D-06 gate.
- Never autonomously execute a destructive/stateful step without just-in-time TA
  permission or TA-runs mode (REC-06).
- Never add a confirm-every-trivial-step ceremony — one plan, one confirm, then
  silent-until-signal (D-10/D-12; the calibration axiom).
- Never claim the evidence gate is tamper-proof — a well-shaped capture exists, it
  is not proven un-forged.
- Never make any `src/dogen/` core/CLI change, add TUI/recorder/sandbox
  dependencies (asciinema/pexpect/rich), or run any git state-changing command; a
  discovered seam gap is a planning-time flag, never a silent core edit.
</must_not>
</constraints>

<output_specification>
The recorded artifact is the CLI-persisted draft (the canonical page(s) under
`docs/`, written by the store in the unit's format) plus the inspectable scratch
workspace, handoff, and report under `.dogen/staging/<id>/`. The whole walk replays
from `git log` alone (the `step-planned` / `step-recorded` / draft transition
commits, with `Dogen-Step` / `Dogen-Verdict` trailers and episode-color bodies).
Report inline:

```
## dogen-record: <unit-id>

- Unit: declared + signed off <author> at <when>
- Steps: <N total — R resolved, U unverified> (all_steps_verified: <true|false>)
- Modes: <agent-runs / TA-runs mix>
- Quality signals: <D deviated, S skipped, F failed> — <episode notes, or (none)>
- Handoff: .dogen/staging/<unit-id>/handoff.<ext> [or handoff/]
- Report: .dogen/staging/<unit-id>/report.yaml
- Recorded draft: docs/<target> [+ each extra target for a multi-file unit]
- Committed: <sha7 from the CLI's `git: committed` line>
- Progress: <progress state>

Next: /dogen-review — review the draft.
```
</output_specification>

<success_criteria>
- [ ] The unit's state was checked first (`record show` + `unit show`); a partial
      step plan offered resume as the default (D-13).
- [ ] The unit was declared and signed off before the walk ran (D-09); an unsigned
      unit was routed to `dogen unit new` + `dogen signoff`, never bypassed.
- [ ] ONE annotated step plan (mode, destructive markers, assumptions inline) was
      proposed, edited conversationally, and persisted with ONE confirmation via
      `dogen record plan --steps-file -` (D-10).
- [ ] The walk ran silent-until-signal (D-12): one status line per step; the TA was
      consulted only at a genuine fork, a permission gate, or a failed step.
- [ ] Agent-runs steps captured verbatim proof (cwd-pinned bytes + sha256 + exit
      code) and recorded via `dogen record step --evidence-file -`; TA-runs steps
      ingested the tee'd file unmodified — no step recorded from a narration.
- [ ] Destructive/stateful steps took just-in-time consent or TA-runs before
      executing; the runtime backstop re-prompted on an unmarked destructive command
      (D-06).
- [ ] Improvisation was recorded as a `deviated` verdict (exit 0) whose reason rode
      the commit body (REC-09 / D-14); frustration surfaced as fail-count/re-plan.
- [ ] The completed walk authored page(s) from curated, env-scrubbed excerpts (D-04),
      staged them, and recorded via `dogen draft --draft-file`/`--draft-dir`
      `--report`; the macro-gate refused with `evidence_incomplete` while any step
      was unverified.
- [ ] Reason codes were surfaced in plain language; the `git: committed <sha7>` line
      was quoted; the TA was routed to dogen-review.
- [ ] Both seam-gap flags were stated; honest framing held throughout; no
      `src/dogen/` change and no git state-changing command were made.
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
</content>
</invoke>
