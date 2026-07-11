---
name: dogen-write
description: Drafts a review-ready, Sphinx-publishable reference page (MyST or rST — the unit's target extension decides) for a declared and signed-off documentation unit by first running the zero-side-effect `dogen draft --resolve-only` provider probe, then branching — a driver provider (copilot or mock) generates in-process via `dogen draft`, while the host-harness passenger authors the page itself, starting from the unit's declared sources and navigating the repo freely, stages it under `.dogen/staging/` together with a context report of everything it read, and records both via `dogen draft --draft-file --report` (or `--draft-dir` for a multi-file unit). The sole skill that may write files, and only the staging files. Use when a TA is ready to draft a signed-off unit.
allowed-tools: Read, Bash, Glob, Grep, Write
---

<objective>
Draft a review-ready, Sphinx-publishable **reference** page for a unit that has
already been declared and signed off, by delegating to the CLI drafting seam and
branching on the resolved provider. **The unit's format is decided by its target
extension** (`format` in `unit show --json`: `.md` → MyST, `.rst` →
reStructuredText) — author in that markup, matching the page's siblings; the
old MyST-only mandate is retired (v1.2). Run the zero-side-effect `dogen draft
--resolve-only` probe first, then branch (D-08): a **driver** (copilot or mock)
generates the draft in-process — this skill just invokes `dogen draft` and reports,
never authoring the text; a **passenger** (host-harness) authors the page itself,
starting from the unit's declared sources and navigating the repo freely from there,
stages it under `.dogen/staging/<id>/` (one handoff file, or a `handoff/`
directory mirroring a multi-file unit's target set), writes a **context report**
of everything it actually read to `.dogen/staging/<id>/report.yaml`, then records
everything via `dogen draft --draft-file --report` (or `--draft-dir`). This is
the **sole** dogen skill that may carry `Write`, and its only permitted writes
are those staging files (D-09 as amended by v1). This skill holds judgment; the
core holds the provable HITL gate (`dogen draft` refuses without a recorded
signoff) and the commit seam (the CLI commits the transition itself — never run
git commands that change state). See `../README.md` for the shared family
contract, glossary, and status vocabulary.
</objective>

<quick_start>
1. Confirm the target unit id. The unit must already be declared and signed off by
   dogen-plan; if `dogen draft` refuses with `signoff_required`, route the TA back
   to dogen-plan.
2. Read the unit's full state: `dogen unit show "$UNIT" --json --latest` — the plan
   (intent, audience, title, sources, target + any `extra_targets`, and
   `format` — the markup you author in), the seeded steering note, every
   appended steering entry (review verdicts land there; a re-draft MUST honour
   them), and the latest generation only (`--latest` keeps old passes' bulky
   read-lists out of your context; `generations_count` still tells you whether
   this is a re-draft).
3. Run the zero-side-effect provider probe:
   `dogen draft "$UNIT" --resolve-only --json`, and read the `provider` field. Do
   NOT probe the environment yourself — the CLI owns provider selection (D-08), and
   selection is explicit (repo config / env / flag; never a silent fallback).
4. Load `references/provider-branch.md` now for the reason-code→branch map, the
   per-format authoring standards (MyST and rST), the stance contract, and the
   report.yaml shape.
5. Branch on the resolved provider (workflow steps 2-3): driver (copilot / mock) →
   `dogen draft`; passenger (host-harness) → author the page(s) in the unit's
   format → stage the handoff and the context report →
   `dogen draft --draft-file --report` (single page) or `--draft-dir` (multi).
6. Report the recorded draft — quoting the CLI's `git: committed <sha7>` line —
   and route the TA to dogen-review.
</quick_start>

<pipeline>
dogen-plan -> dogen-write -> dogen-review

This skill is the drafting stage. It consumes a declared+signed-off unit and
produces a recorded draft (via `dogen draft`, advancing `progress -> drafted`; the
CLI's commit seam records the transition). Routing rules:

- On success it hands off to dogen-review with the frozen referral line
  (`Next: /dogen-review — review the draft.`).
- If `dogen draft` refuses with `signoff_required`, route back to dogen-plan.
- The provable HITL gate is the core's — this skill calls the CLI and branches on its
  reason codes; it never re-implements the gate.
- `Write` is used ONLY for the passenger staging files under `.dogen/staging/<id>/`.
- The CLI commits transitions itself; this skill never commits, stages, or pushes.
</pipeline>

<workflow>
<step_1 name="Read the unit state and probe the provider">
Confirm the unit id, then read the full unit state:

```bash
dogen unit show "$UNIT_ID" --json --latest
```

Take from it: intent, audience, title, the declared `sources` (with their commit
stamps), `sphinx_target` (where the page will land — the plan's placement
decision, never yours to override), any `extra_targets` (a multi-file unit's
additional pages — the whole set gets drafted together), the `format` field
(the markup you author in: `myst` or `rst` — decided by the target extension,
matching the page's siblings), the seeded `steering_notes`, and every entry
in the `steering` stream — review-verdict entries are corrections a re-draft
MUST apply.

**Re-draft precondition:** when `generations_count` ≥ 1 this is a re-draft, and
the correction that motivates it must already be RECORDED — a review
fix/redraft verdict or a `dogen steer --note` entry newer than the last
generation. If the steering stream holds nothing new, STOP and route back: the
reviewer records the verdict first (dogen-review), or the TA records a note
(`dogen steer`). Never apply corrections carried only in conversation — the
draft output's `unsteered_redraft: true` flag means exactly that miss. Then run
the zero-side-effect probe:

```bash
dogen draft "$UNIT_ID" --resolve-only --json
```

Read the `provider` field from the JSON (`copilot` / `mock` / `host-harness`). This
call has no side effects — no gate, no generation, no writes (D-07). The resolved
name is the single branch signal (D-08). Load `references/provider-branch.md` now.
</step_1>

<step_2 name="Driver branch (copilot / mock)">
If the resolved provider is `copilot` or `mock`, the provider generates the draft
in-process behind its bounded READONLY toolset and reports its own reads. Invoke the
drafting seam and report; do NOT author or `Write` anything:

```bash
dogen draft "$UNIT_ID" --json
```

Read the result. Map any failure reason to plain-language TA guidance
(`signoff_required` → route to dogen-plan; `backend_unavailable` → the Copilot
backend is unreachable; `model_rejected` → the requested model was refused) per
`references/provider-branch.md`. In this branch the skill never uses `Write`.
</step_2>

<step_3 name="Passenger branch (host-harness)">
If the resolved provider is `host-harness`, the host authors the page(s) itself,
**in the unit's format** (the `format` field: MyST for `.md`, reStructuredText
for `.rst` — the per-format standard is in `references/provider-branch.md`).

1. **Ground the draft.** Start from the unit's declared `sources` — read them in
   full; they are the primary grounding. Then navigate the repo freely wherever a
   fact's origin lies (implementations, fixtures, sibling docs, the repo's existing
   documentation conventions, and any `.dogen/context/` artifacts): the declared
   sources are starting points, not a boundary (v1). **When the plan outline names
   an inventory** (e.g. a per-interface attribute table, one row per member), that
   inventory is a **read contract**: locate and read the authoritative source for
   *every* member before authoring — a cross-reference to a sibling page is not a
   substitute for reading and materializing the inventory here (round 3: a leg that
   never read the seven interface files punted them to a `:ref:` and lost the
   coverage). Never assert what you have not read. Keep a running list of every file
   you read — it becomes the context report.
2. **Author** a Sphinx-publishable **reference** page per the format's authoring
   standard and the stance contract in `references/provider-branch.md`. Facts you
   cannot verify at their origin are left out of the prose and recorded as `gaps`
   in the report — never hedged into the page as corpus-narration. A multi-file
   unit authors every page in its set; each page follows its own extension's
   format, and cross-page terminology and links stay consistent across the set.
3. **Coverage check (before writing anything):** walk the unit plan's
   `## Outline / acceptance` items one by one against the authored page(s) —
   per page for a multi-file unit. Every coverage item is either present or
   recorded as a `gap` with the reason — never silently dropped. What you read
   must convert: if you read an inventory (e.g. every interface's reference
   file), the page carries the inventory; reading without converting is the
   worst validation failure mode. Also check every relative include/link path
   resolves **from each page's committed location** (`docs/<target>` — mind the
   directory depth).
4. **Stance check:** grep the authored page(s) for the banned researcher register,
   for implementation identifiers (type/function names, `internal/` paths), and
   for runtime-mechanics narration (temp files, interpreter invocations,
   internal process flow — implementation, not interface, even in declarative
   voice). Fix every hit before handing off.
5. `Write` the authored page(s). Single-page unit: the handoff file, named with
   the target's own extension — `.dogen/staging/<UNIT_ID>/handoff.<ext>`.
   Multi-file unit: a `handoff/` directory mirroring the target set —
   `.dogen/staging/<UNIT_ID>/handoff/<target-relpath>` for EVERY page in the
   set (the CLI refuses a missing page as `handoff_incomplete` and a stray one
   as `undeclared_target`).
6. `Write` the context report to `.dogen/staging/<UNIT_ID>/report.yaml` — every
   file read (commit-stamped via one `git rev-parse HEAD`; a stamp is a hex SHA
   or honestly empty — explanations go in an origin's `note` field), the tools
   used, and any confidence gaps. **An empty `gaps` list requires a one-line
   `gaps_note` justification** — "nothing unverified" is a claim, not a
   default. These staging files are the ONLY files this skill writes (D-09/v1);
   all are left in place so the TA can inspect exactly what was handed off and
   what grounded it (they are gitignored via the seeded `.dogen/.gitignore`, so
   they never leak into anyone's commits).
7. **Self-assert the model first (D-01).** The model is a persisted repo fact,
   resolved by dogen at `--model` flag > `DOGEN_MODEL` env > repo config — you no
   longer force `--model` on every draft once the config carries it. Check what
   the repo already holds with `dogen model show --json` (`model` / `source` /
   `model_origin`), then settle it once per repo:
   - **No model in the repo config** → silently self-assert it by running
     `dogen model set "$HOST_MODEL" --origin self`, then narrate **exactly one**
     correctable line (substitute the real name for `X`): recording model X (self-asserted) — correct me if wrong. It does **not** block and does **not** gate on a TA confirmation — the line invites a correction, it does not wait for one.
   - **A model is already in the repo config** → use it silently. Do not
     re-assert it and do not reflect it back — the persisted fact stands.
   - **You genuinely cannot name your own model** → ask the TA once as a
     **fallback** (they can read it off their harness UI) and, on their answer,
     `dogen model set "<name>" --origin self`. If the TA can't or won't name it
     either, record honest-empty — `model_unrecorded` fires downstream (still
     legal; see below).
   - **A TA correction** (the corollary of "correct me if wrong") → re-run
     `dogen model set "<corrected>" --origin ta`: the origin flips to `ta`
     because a human vouched for the value.

8. Record everything through the CLI (the model now resolves from config by
   flag > env > config — pass `--model` only to override it for this one draft):

```bash
# Single-page unit:
dogen draft "$UNIT_ID" \
  --draft-file ".dogen/staging/$UNIT_ID/handoff.$EXT" \
  --report ".dogen/staging/$UNIT_ID/report.yaml" \
  --provider host-harness --json
# Multi-file unit:
dogen draft "$UNIT_ID" \
  --draft-dir ".dogen/staging/$UNIT_ID/handoff" \
  --report ".dogen/staging/$UNIT_ID/report.yaml" \
  --provider host-harness --json
```

Read the result and surface it — if it carries `model_unrecorded: true`, the
model was recorded empty (the repo config carried none and neither the self-assert
nor the TA fallback named one; round 3's opencode leg recorded `''` on all three
passes by never self-asserting). Self-assert it now — `dogen model set <name>
--origin self` (or `--origin ta` for a TA-supplied name) — then `dogen draft
"$UNIT_ID" --amend-model <name>` to stamp the already-recorded generation, or
state plainly that the model is unknown.
</step_3>

<step_4 name="Report and route">
Report the recorded draft (provider, resulting progress state) from the `--json`
output, and quote the CLI's `git: committed <sha7> — …` stderr line (the same
hash arrives as `commit` in the JSON) — the transition commit is the audit
anchor; never assert "the seam committed it" without the hash. If the output
carries `stale_plan: true`, tell the TA plainly: the unit's plan changed after
its signoff — the draft ran, but they should re-approve the plan (that is
`dogen signoff --re-sign`, or folded into a future amendment via
`dogen unit edit … --re-sign`) if the change was substantive. On success, route
the TA to dogen-review. Do not commit, stage, push, or build — the CLI's commit
seam already recorded the transition. Optionally show the TA what was drafted
before handing off to review.
</step_4>
</workflow>

<edge_cases>
**Unit not signed off (`signoff_required`):** `dogen draft` refuses (the HITL gate).
Route the TA back to dogen-plan to complete the plan and sign it off; do not attempt
to bypass the gate.

**`backend_unavailable` / `model_rejected` (driver):** surface the reason in plain
language; for `model_rejected` name the requested model. Offer to retry (e.g. without
a specific `--model`) or route as appropriate. Do not fall back to authoring in the
driver branch.

**Passenger with a hidden host model:** self-assert the model first —
`dogen model set <name> --origin self` (persisted once per repo, narrated with the
one correctable line). Only when you genuinely cannot name your own model do you
ask the TA as a fallback; if the TA can't say either, record honest-empty — the
empty (unknown) model plus `mode=passenger` keeps provenance honest (D-01/D-12),
and the draft's `model_unrecorded: true` flag records that the gap was surfaced,
not missed.

**`unsteered_redraft: true` in the draft output:** the re-draft ran with no
recorded steering or verdict since the last generation — the correction lived
only in conversation. Surface it and get the correction recorded now
(`dogen review --verdict fix` or `dogen steer --note`) so the audit trail
matches what actually steered the pass.

**`stale_plan: true` in the draft output:** the plan was edited after signoff. Not an
error — surface it and suggest `dogen signoff --re-sign` when the change was
substantive.

**A load-bearing file outside the declared sources:** read it (free navigation is the
v1 policy), record it in the context report, and suggest the TA promote it:
`dogen unit edit "$UNIT_ID" --add-source <path>`.

**A fact you cannot verify anywhere you can read:** leave it out of the prose and
record it under `gaps` in the report — a gap is provenance, not content.
</edge_cases>

<constraints>
<must>
- Read the unit state first (`dogen unit show --json --latest`) and honour every
  steering entry — review-verdict entries are binding corrections for a re-draft.
- On a re-draft, require the correction to be RECORDED (a fix/redraft verdict or
  a steer note newer than the last generation) before drafting; never apply
  corrections carried only in conversation.
- Check every plan outline/acceptance item off against the authored page
  (present, or a recorded gap with a reason) and verify relative include/link
  paths resolve from `docs/<sphinx_target>` before handing off.
- Run `dogen draft --resolve-only --json` and branch on the CLI-reported provider
  name (D-08) — never a skill-side environment/capability probe.
- In the passenger branch, start from the declared sources, navigate freely from
  there, and record EVERY file read in the context report with its commit stamp —
  ground every claim in something actually read (v1).
- Follow the stance contract: write as the product's reference, never as a
  researcher describing their evidence; unverifiable facts become report `gaps`,
  never hedged prose. The full contract lives in `references/provider-branch.md`
  (canonical: `dogen.core.authoring.STANCE_CONTRACT`).
- Author Sphinx-publishable pages for the **reference** Diataxis direction **in
  the unit's format** (`format` from `unit show --json`): MyST with
  `colon_fence` for `.md`, reStructuredText for `.rst` — per the per-format
  standards in `references/provider-branch.md`. Never write one markup into the
  other's extension.
- Justify an empty `gaps` list with a one-line `gaps_note` in the report;
  self-assert the model once per repo (`dogen model set --origin self` + the one
  correctable line), asking the TA only as a fallback before recording
  honest-empty.
- Reference code entities by qualified name; show a code block only when the reader
  themselves authors or invokes it — the code-in-narrative rubric in
  `references/provider-branch.md`.
- Record every draft through the CLI (`dogen draft`), which owns the provable HITL
  gate and the commit seam; surface its reason codes in plain language per
  `../README.md`.
- Self-assert the model first in the passenger branch (`dogen model set
  --origin self`, persisted once per repo) so it resolves from config by
  flag > env > config; ask the TA only as a fallback, and leave the model
  honestly unknown (empty) only when neither can name it (D-01/D-12).
</must>
<must_not>
- D-09 (v1): Never use `Write` anywhere except the passenger staging files —
  the handoff (`.dogen/staging/<id>/handoff.<ext>`, or
  `.dogen/staging/<id>/handoff/<target>` per page for a multi-file unit) and
  `.dogen/staging/<id>/report.yaml`. In the driver branch the skill never
  writes.
- Never `Write` the canonical draft to `docs/` or edit `unit.md` — the store writes
  the canonical `docs/` output; plan amendments go through `dogen unit edit`.
- Never re-implement the HITL gate or bypass a `signoff_required` refusal.
- Never commit, stage, push, build, or publish — the CLI's commit seam owns the
  transition commit.
- Never assert a fact you have not read at its origin; never narrate your evidence
  ("observed", "the fixtures show", "every observed use") in the drafted prose.
- Never reproduce implementation bodies, private internals, or verbatim
  struct/function source in the drafted page — reference them by qualified name.
</must_not>
</constraints>

<output_specification>
The recorded artifact is the CLI-persisted draft (the canonical page(s) under
`docs/`, written by the store in the unit's format) plus, in the passenger
branch, the inspectable handoff and report under `.dogen/staging/<id>/`. Report
inline:

```
## dogen-write: <unit-id>

- Provider: <copilot | mock | host-harness>
- Handoff (passenger only): .dogen/staging/<unit-id>/handoff.<ext> [or handoff/]
- Report (passenger only): .dogen/staging/<unit-id>/report.yaml
- Recorded draft: docs/<sphinx_target> [+ each extra target for a multi-file unit]
- Committed: <sha7 from the CLI's `git: committed` line>
- Progress: <progress state>
- Plan: <fresh | changed since signoff — re-approve if substantive>
- Model: <recorded model (self-asserted / TA-corrected) | unknown — neither self nor TA could name it>

Next: /dogen-review — review the draft.
```
</output_specification>

<success_criteria>
- [ ] The unit state (plan + steering stream) was read first and every steering
      entry honoured.
- [ ] `dogen draft --resolve-only` was run and the branch keyed off the
      CLI-reported provider name (D-08).
- [ ] Driver branch invoked `dogen draft` and reported; the skill wrote nothing.
- [ ] Passenger branch grounded the draft starting from the declared sources with
      free navigation beyond them, authored in the unit's format (per-page for a
      multi-file unit), wrote ONLY the handoff file(s) and the context report
      under `.dogen/staging/<id>/`, and recorded via
      `dogen draft --draft-file`/`--draft-dir` `--report` after self-asserting
      the model once per repo (`dogen model set --origin self`), asking the TA
      only as a fallback (D-01/D-12).
- [ ] The context report lists every file read (hex-or-empty commit stamps,
      explanations in `note`) and honest gaps — or a `gaps_note` justifying an
      empty list; the drafted prose carries no researcher register, no
      implementation identifiers, and no runtime-mechanics narration.
- [ ] Every plan outline/acceptance item was checked off against the page
      (present or a recorded gap); reading converted into coverage.
- [ ] On a re-draft, the recorded steering stream held the correction BEFORE the
      pass ran (no `unsteered_redraft` flag).
- [ ] Reason codes were surfaced in plain language; `signoff_required` routed back
      to dogen-plan; `stale_plan` was surfaced when present.
- [ ] On success the TA was routed to dogen-review; the skill ran no git
      state-changing command (the CLI's seam owns the commit).
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
