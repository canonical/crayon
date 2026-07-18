# dogen skill family contract

The **normative family contract** for the portable Agent Skills vendored in this
directory. Portable `SKILL.md` files are dogen's primary human-facing surface — the
loop a Technical Author (TA) actually drives, layered over the deterministic Python
core. Every `dogen-*` skill follows this contract; `<self_healing>` updates must
preserve it.

The skills are conversational LLM prompts (no flags) that shell into the locked
CLI seam (`dogen unit new|edit|show` / `dogen signoff` / `dogen steer` /
`dogen draft` / `dogen review` / `dogen status` / `dogen context`) via `Bash`. The
skills carry **intent and judgment**; the CLI holds the **provable HITL gate** and
the **commit seam** — a skill never re-implements a gated, side-effecting action,
it delegates it, and it never runs a git state-changing command (the CLI commits
every lifecycle transition itself, with `Dogen-Unit`/`Dogen-Phase` trailers, so a
unit's whole path is reconstructable from `git log` alone).

This README is the **maintainer source of truth**. The agentskills.io loading model
auto-loads each `SKILL.md` (plus its on-demand `references/`) but never this README,
so anything a skill must execute at runtime — notably the `<self_healing>` block —
is physically embedded in each `SKILL.md`, byte-identical (D-02).

Install the family into a harness with `dogen skills install` (see "Installation"
below) — this canonical directory is the single source; per-harness staging is the
install flow's job, never a hand-copy.

## Pipeline

```
dogen-plan -> dogen-write -> dogen-review
```

- **dogen-plan** — grounds itself in the repo's prior art (`.dogen/context/`
  artifacts — doc-style, glossary, structure, code-to-docs map, doc-gaps — and
  existing docs conventions), runs the Socratic intake, declares the
  unit, and ends with the gate act. Also serves advise-only triage asks ("does
  this need docs?") with a grounded Triage Recommendation, declaring nothing
  until the TA says go. Maps to `dogen unit new … --notes …` (+
  `dogen unit edit` for amendments — never a clobber) then `dogen signoff`.
  Write/Edit-free.
- **dogen-write** — drafts the page in the unit's format (MyST or rST — the
  target extension decides, v1.2). Branches on `dogen draft --resolve-only`
  (driver vs passenger). The passenger starts from the declared sources, navigates
  the repo freely, and records **everything it read** in a context report. It is
  one of the **two draft-stage skills** (with dogen-record) that may carry
  `Write`, for exactly two staging files:
  `.dogen/staging/<id>/handoff.<ext>` and `.dogen/staging/<id>/report.yaml`.
  dogen-write is the draft-stage skill for **reference** units; dogen-record is
  its actionable-unit counterpart.
- **dogen-record** — the draft-stage skill for **actionable** (tutorial / how-to)
  units: it walks the procedure step by step, recording evidence under the
  Phase-12 `record` gate (`dogen record plan|step|show`), then authors and stages
  the page exactly as dogen-write's passenger does
  (`dogen draft --draft-file/--draft-dir --report`). The second draft-stage skill
  that may carry `Write` (staging-only) — the alternative to dogen-write, not a
  replacement. **Interim entry (Phase 13):** dogen-record needs a declared +
  signed-off unit, the same precondition as dogen-write; until Phase 14 wires
  dogen-plan's type routing, the TA declares an actionable unit directly via
  `dogen unit new` then `dogen signoff` (this phase touches dogen-plan zero).
- **dogen-review** — presents a provenance summary (and, in review mode, grounded
  five-dimension findings — writing-approach always on, opened by a
  deterministic read-only pre-pass, numbered `F-N` with a recommended verdict
  derived from the tally), records the structured verdict via
  `dogen review --verdict accept|fix|redraft --note` (or `--note-file -` to read a
  quote-heavy / multi-line note from stdin — exactly one of `--note`/`--note-file`),
  and stops. `accept` seals the
  exact draft text; `fix`/`redraft` land the note in the unit's steering stream for
  the next pass — a `fix` is a bounded correction ("apply the recorded fix"), a
  `redraft` is a fresh pass ("re-draft"); they never share wording (M2).
  Write/Edit-free.

Routing rules:

- dogen-plan hands off to dogen-write once the unit is declared and signed off.
- dogen-record is the draft-stage alternative for **actionable** units: from the
  same declared + signed-off precondition it walks the procedure, records the
  draft, and hands off to dogen-review. Phase 14 wires dogen-plan's type routing
  to it; in Phase 13 the TA enters it directly (the interim entry above).
- dogen-write hands off to dogen-review once a draft is recorded.
- dogen-review routes fix/redraft verdicts back to dogen-write (the note is already
  in the steering stream; it never edits the draft itself — the reviewer owns the
  output, project principle).
- No skill builds, publishes, pushes, or runs git state-changing commands. The
  CLI's commit seam records every transition locally; the human owns publishing.

## SKILL.md skeleton

Sections appear in exactly this order (lifted from a proven production
docs-skill family shape, adapted to three skills):

1. **YAML frontmatter** — `name` (MUST equal the directory name),
   `description` (a single line; capability first, then a trigger sentence
   starting "Use when …"; **no `<`/`>` angle brackets** — they are a spec
   injection surface), and `allowed-tools` (an explicit comma list). `Write` and
   `Edit` are **excluded** from the delegating skills (dogen-plan and dogen-review
   — all but the two draft-stage writers); only dogen-write and dogen-record may
   list `Write`.
2. `<objective>` — what the skill does and its non-negotiable philosophy.
3. `<quick_start>` — numbered entry point; BLOCKING input-collection lists live here.
4. `<pipeline>` — the shared flow line above plus this skill's consumes/produces
   and routing rules.
5. `<workflow>` — numbered `<step_N name="Sentence case name">` elements.
6. `<examples>` and/or `<edge_cases>` — optional.
7. `<constraints>` — `<must>` and `<must_not>` bullet lists. Phase-decision
   citations (D-NN) are preserved byte-identical across edits.
8. `<output_specification>` — every skill keeps the close-border skeleton here:
   the `git: committed <sha7>` relay line(s) and the frozen referral (SK-05).
   The recorded artifact may itself be CLI-persisted (dogen-plan's is the unit
   and its signoff act), but the close block is mandatory in all three skills.
9. `<success_criteria>` — measurable `- [ ]` checklist.
10. `<self_healing>` — the canonical block below, byte-identical in every skill.

**File-shape invariants** (enforced by `scripts/skill_lint.py`, D-18):

- Frontmatter `name:` equals the directory name for every skill.
- `dogen-plan` and `dogen-review` `allowed-tools` **exclude** `Write` and `Edit`
  (only the two draft-stage writers, dogen-write and dogen-record, may list
  `Write`) — the delegation to the CLI (and, for review, back to dogen-write) is
  enforced at the tool surface, a provable invariant in code, not authoring
  discipline.
- `description:` is present, non-empty, and carries no angle brackets.

## references/ files

Each reference file's first body line is:

```
Load this file at workflow step N (Name).
```

and the corresponding `SKILL.md` step says `Load references/<file> now.` References
hold relocated detail (intake checklists and the Socratic technique,
reason-code→branch maps, the authoring standard, writing standards, and stance
contract, provenance field maps, the review rubric); the `SKILL.md` keeps the
decision logic. Keep each reference small and self-labeled — Copilot eager-loads
references, Claude lazy-loads them.

Two reference sections are **governed mirrors** of core constants, bound by drift
guards: the code-in-narrative rubric (`dogen.core.authoring.REFERENCE_CODE_RUBRIC`)
and the stance contract (`dogen.core.authoring.STANCE_CONTRACT`). Edit the core
symbol and the mirror together, never one alone.

## Glossary

- **TA / user** — the Technical Author driving the session (never "operator").
- **unit** — one documentation unit: the editable `unit.md` plus its sidecar
  `provenance.yaml` / `progress.yaml` under `.dogen/units/<id>/`.
- **signoff** — the recorded HITL gate act (`dogen signoff`): author, timestamp,
  and a content hash of the exact `unit.md` approved. It provably precedes any
  draft; a later plan edit surfaces as a **stale plan** until re-signed.
- **steering stream** — the append-only guidance entries (`provenance.yaml:
  steering`): manual `dogen steer --note` entries plus automatic fix/redraft
  review-verdict entries. The next draft pass reads the whole stream. Distinct
  from the signoff — guidance flows freely, the gate act is deliberate.
- **provenance** — the on-disk audit sidecar (`provenance.yaml`): the signoff, the
  steering stream, and per-generation records — provider, mode, model, what the
  writer actually read (`context_origins`, commit-stamped) versus the declared
  `sources`, the writer's declared `gaps`, the draft path/hash, and the recorded
  reviews.
- **context report** — the passenger's self-report (`report.yaml` next to the
  handoff): everything read (commit-stamped), tools used, and gaps. Ingested via
  `dogen draft --report`; the uniform provenance contract across providers. It
  parses leniently (YAML, then JSON) — a broken report reports the YAML parser's
  line/column plus a hint to quote any scalar containing `::`; `dogen report
  template <id>` prints a valid, unit-aware skeleton (`--write` lands it).
- **driver** — a provider that generates in-process (Copilot SDK, or `mock`);
  dogen-write invokes `dogen draft` and reports, never authoring the text itself.
- **passenger** — the `host-harness` provider; the host agent authors the page
  itself (in the unit's format) and hands it (plus its context report) to
  `dogen draft --draft-file --report`.
- **handoff file** — the passenger's authored page at
  `.dogen/staging/<id>/handoff.<ext>` (the target's extension), left in place for
  inspection. For a multi-page unit, `dogen staging plan <id>` prints the expected
  `handoff/<relpath>` tree and marks each page ✓ staged / missing (`--scaffold`
  creates only the missing placeholders — never clobbering a staged draft).
- **HITL gate** — the provable, core-enforced rule that `dogen draft` refuses
  without a recorded signoff. The gate lives in the core; skills surface it.
- **commit seam** — the CLI-owned rule that every lifecycle transition records one
  local commit with `Dogen-Unit` / `Dogen-Phase` / `Dogen-Run` trailers
  (configurable via `dogen commits auto|off` and `--no-commit`). Skills never
  commit; the seam never pushes or publishes.
- **verdict** — the structured review outcome (`accept` / `fix` / `redraft`).
  `accept` seals the exact draft text (its hash lands on the review record);
  `fix` and `redraft` append the note to the steering stream **identically** —
  they differ only in the recorded verdict and the routing wording (a `fix`
  "applies the recorded fix"; a `redraft` "re-drafts from scratch"). Neither
  edits the draft; the next `dogen draft` reads the note.
- **progress states** — the unit lifecycle: `pending → sourced → drafted →
  reviewed` (plus the reserved `committed`, which no command sets — the human
  owns publishing).

## Status vocabulary

The family's shared status language **is the CLI's existing machine surface,
verbatim** (D-03). Skills surface these codes; they do **not** invent a parallel
per-skill taxonomy. Single source of truth, zero skill↔core drift.

**Failure `reason` codes** (emitted in `dogen … --json` on failure):

| reason | meaning |
|--------|---------|
| `signoff_required` | `dogen draft` refused — the unit has no recorded signoff (the HITL gate). |
| `signoff_exists` | `dogen signoff` refused — the act already exists; pass `--re-sign` to overwrite deliberately. |
| `backend_unavailable` | the Copilot backend could not be reached. |
| `model_rejected` | the requested model was refused by the backend. |
| `unit_exists` | the unit's existence state is the obstacle — a clobber refusal in `unit new`, or a not-found unit in `signoff`/`steer`/`draft`/`review`. |
| `unit_not_found` | a lifecycle verb (`unit edit`/`rm`/`mv`/`show`) targeted a unit that does not exist. |
| `confirm_required` | `unit rm` was invoked without `--force` (the verb is non-interactive). |
| `not_drafted` | `dogen review` refused — the unit has not been drafted yet. |
| `already_accepted` | `dogen review --verdict accept` refused — the latest sealed accept already covers this identical draft (nothing was recorded). |
| `target_exists` | `dogen unit edit --target` refused — a file already exists at the new output path (the draft move never clobbers). |
| `bad_target` | `unit new`/`unit edit` refused — the target carries no supported page extension (`.md`/`.rst`; the extension IS the unit's format, v1.2). |
| `target_claimed` | `unit new`/`unit edit` refused — the docs target already belongs to another unit's page set (v1.2). |
| `bad_report` | `dogen draft --report` refused — the context report failed validation (unreadable YAML, or a commit stamp that is neither hex nor empty; explanations belong in an origin's `note`). |
| `handoff_incomplete` | `dogen draft --draft-dir` refused — a declared target has no staged file (v1.2). The error enumerates each `expected: handoff/<relpath>`; **move** the page into place (a flat handoff with unique basenames is now accepted and mapped by basename) — never delete a staged draft to fix layout. |
| `undeclared_target` | `dogen draft --draft-dir` refused — a staged file matches no declared target (v1.2). Move the stray file to its `handoff/<relpath>` or amend the plan (`--also-target`); do not delete staged drafts. |
| `multi_target_unsupported` | `dogen draft` refused — a driver provider was asked to draft a multi-file unit; route through the host-harness passenger (v1.2). |
| `model_already_set` | `dogen draft --amend-model` refused — the latest generation already records a vouched model; amend fills only an empty slot and never overwrites (MODEL-02 / D-04). |
| `schema_unsupported` | `dogen unit show` refused — a provenance record declares a `schema_version` newer than this tool supports (D-08); the message names found vs supported. |
| `provenance_invalid` | `dogen unit show` refused — a present provenance sidecar failed to parse/validate (D-09), distinct from `unit_not_found`. |

**Success-object fields worth surfacing:** `stale_plan: true` on a `draft` result
means `unit.md` changed after its signoff — surface it and suggest re-approving
(`dogen signoff --re-sign`, or fold it into the amendment next time with
`dogen unit edit … --re-sign`). `unsteered_redraft: true` on a
`draft` result means a re-draft ran with no recorded steering or review verdict
since the last generation — get the correction recorded so the audit trail shows
what steered the pass. `model_unrecorded: true` on a `draft` result means the
generation recorded an empty model — no model in the repo config and neither the
self-assert nor the TA fallback named one; get it recorded (see the model
self-assert rule in dogen-write, then `dogen draft … --amend-model`).
`unapplied_steering: true` on a `review` accept means a correction was recorded
after the last draft and never drafted against — it was sealed over; only accept
over it deliberately. `commit` on any state-changing verb is the transition
commit's hash (also printed as a `git: committed <sha7> — …` stderr line) —
quote it in your closing summary so the transcript carries the audit anchor.

A `note: target normalized (leading docs/ stripped): …` line on a `unit new` /
`unit edit` is dogen correcting a docs-relative target that carried a stray
`docs/` prefix (it would otherwise land at `docs/docs/…`). Relay it plainly and
carry on — the stored target is the corrected one.

## Routing language (`next_id` → the frozen referral line, v1.3)

`dogen review --json` and `dogen status --json` carry a machine routing token,
`next_id`, beside the human `next` string. **Translate the token into the loop's
language; never parrot the raw `next` line to the TA** — it speaks CLI (round
2's "Next: dogen draft …" leaks), and the TA drives skills, not verbs.

Round 3 showed the translation itself drifted — each leg reworded the referral
(bare vs backticked vs bold skill name, "invoke" vs "ready for", no slash
anywhere). The referral is now a **frozen grammar**, identical across every skill
and every harness:

```
Next: /dogen-<skill> — <one imperative clause>.
```

Rules (all three are load-bearing — round 3 broke each at least once):

- **Always the slash form** (`/dogen-write`, `/dogen-review`, `/dogen-plan`) —
  it is how the TA invokes a skill on every supported harness; naming the skill
  without the slash makes the TA guess.
- **A definite imperative** — "apply the recorded fix", "review the draft". Never
  hedge ("you may want to…", "ready for dogen-write to…", "you could run…").
- **Offer a choice only at a genuine fork** — and then present labeled options
  with a recommended default (the smart-defaults rule below), never an open
  question.

The frozen line per token — note `draft` splits on the **last verdict** (M2), so
a bounded fix never reads as a from-scratch re-draft:

| `next_id` (context) | the exact line |
|---------------------|----------------|
| `draft` (after a `fix` verdict) | `Next: /dogen-write — apply the recorded fix.` |
| `draft` (after a `redraft` verdict) | `Next: /dogen-write — re-draft against the recorded steering.` |
| `draft` (first draft, freshly signed off) | `Next: /dogen-write — draft the unit.` |
| `review` | `Next: /dogen-review — review the draft.` |
| `sign_off` | `Next: /dogen-plan — approve the plan (signoff) so drafting can start.` |
| `re_sign` | `Next: the plan changed since signoff — re-approve it (I can fold that into the amendment with \`dogen unit edit … --re-sign\`), then /dogen-write.` |
| `publish` | `Next: accepted — the publishing commit is yours.` |
| `done` | `Next: nothing pending for this unit.` |

The draft-stage fork now has two entries — one per draft-stage writer. For a
**reference** unit the draft-stage referral stays `Next: /dogen-write — draft the
unit.`; for an **actionable** (tutorial / how-to) unit it is
`Next: /dogen-record — walk the procedure and record the draft.` (same frozen
grammar, the slash form and a definite imperative). Phase 14 wires dogen-plan's
type routing to emit the matching `next_id` at signoff; in Phase 13 the TA enters
dogen-record directly per the interim entry (`dogen unit new` → `dogen signoff`).

The raw `next` string stays available for audits; quoting it is fine when the TA
explicitly asks what the CLI said. Reason codes and progress states remain
surfaced **verbatim** (D-03) — the frozen grammar covers routing only.

## Smart defaults (family-wide, v1.2)

Every mechanical field a skill needs — title, target path, format,
review mode, verdict — is **proposed with an evidence-grounded recommendation
and presented as labeled choices** the TA confirms or overrides; never make
the TA type a value the skill can derive (round 2's copilot leg is the proven
shape; asking a question whose answer the skill has already argued for is the
anti-pattern — propose it as the default instead). When only one option is
defensible, state it and the reason, and proceed unless the TA objects.
dogen-review's recommended verdict is this rule applied to its findings tally:
any must-fix → fix (redraft when the must-fixes are pervasive); should-fix
only → genuinely the TA's call; clean → accept.

The **unit id** is the one exception — its authority runs the other way:
A TA- or brief-supplied unit id is used verbatim; propose an id only when none is supplied.

**Progress states** (the `progress` field): `pending → sourced → drafted →
reviewed` (reserved terminal: `committed`).

**Verdicts** (the `--verdict` values): `accept` / `fix` / `redraft` — the CLI's own
vocabulary, surfaced verbatim; a separate axis from both the reason codes and the
review-findings priorities (must-fix / should-fix / nit).

A skill reads these from `--json` output and maps them to plain-language TA
guidance; it never coins its own status words.

## Provider selection (explicit, v1)

Selection is explicit: `--provider` flag > `DOGEN_PROVIDER` env > repo config
(`dogen provider set`, default `host-harness`) > built-in `host-harness`. There is
no `auto` and no silent capability fallback; `dogen provider show` explains the
effective resolution and whether the Copilot driver would be viable (diagnostic
only). Skills never probe the environment — `dogen draft --resolve-only --json` is
the single branch signal.

## Model selection (persisted + self-asserted, v1.1)

The drafting model is a **persisted repo fact**, not a per-session ask. `dogen
model show|set <name> [--origin ta|self]` mirrors `provider show|set`, and draft
resolution is explicit: `--model` flag > `DOGEN_MODEL` env > repo config (`dogen
model set`) — `model_unrecorded` fires only when all three are absent.

dogen-write **self-asserts first** (D-01): with no model in config it silently
runs `dogen model set <name> --origin self` **once per repo** and narrates one
correctable line ("recording model X (self-asserted) — correct me if wrong"); an
existing config model is used silently (no re-assert, no re-ask); the TA is asked
only as a fallback when the agent cannot name itself; honest-empty is the last
resort. A TA correction re-runs `dogen model set <name> --origin ta` (a human
vouched, so the origin flips to `ta`). A model forgotten on an already-recorded
generation is patched with `dogen draft <id> --amend-model <name>` — a
metadata-only `model-amended` commit, never a new generation.

The `model_origin` — `ta` / `self` / `config` / `flag` / empty (D-03: who
vouched) — rides onto the generation and surfaces in dogen-review's provenance
summary alongside provider/mode/model, so a reviewer sees on whose authority the
model was recorded.

## Installation

The canonical family lives here (`skills/`). `dogen skills install
[--harness claude|copilot|opencode]` stages byte-identical copies into the chosen
harness's discovery root, applies any minimal per-harness tailoring, and records a
manifest (`.dogen/skills-install.yaml`) with content hashes so `dogen skills
status` can detect drift and `dogen skills update` can refresh. Never hand-copy or
symlink the skills; the install flow is the supported path.

## Non-destructive default

Skills are conversational LLM prompts with no `--apply`/`--json`/`--language`
flags, and they never build, publish, push, or run git state-changing commands
(the CLI's commit seam owns the transition commits). The narrow write carve-out
in the family belongs to the **two draft-stage skills** — dogen-write's passenger
branch and dogen-record's walk — each of which writes the authored page handoff
and its context report under `.dogen/staging/<id>/` before calling
`dogen draft --draft-file/--draft-dir --report` — announced in the conversation,
left in place for inspection. Every other persistence goes through the CLI verbs,
which own the provable gate.

## Canonical self_healing block

Embedded byte-identical in every `SKILL.md` (D-02):

```
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
```

## Licensing

The skills in this directory are licensed under **Apache-2.0** (see [`LICENSE`](./LICENSE)),
separate from the LGPL-3.0-only packaged core. This license is not bundled into the wheel.
