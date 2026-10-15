# crayon skill family contract

The **normative family contract** for the portable Agent Skills vendored in this
directory. Portable `SKILL.md` files are crayon's primary human-facing surface — the
loop a Technical Author (TA) actually drives, backed by one deterministic tool that
enforces the load-bearing guarantees. Every `crayon-*` skill follows this contract.

The skills are conversational LLM prompts (no flags of their own) that invoke the
single `crayon` executable via `Bash`. The skills carry **intent and judgment**; the
tool holds the **provable HITL gate**, the write protocol, the evidence gate, and the
**commit seam** — a skill never re-implements a gated, side-effecting action, it
delegates it, and it never decides where the loop goes.

This README is the **maintainer source of truth**. The agentskills.io loading model
auto-loads each `SKILL.md` and its `references/` but never this README, so anything a
skill must execute at runtime is physically embedded in each skill directory.

## Pipeline

```
crayon-onboard (repo walk, occasional) ─┐
crayon-fetch (declared sources, occasional) ─┴─> .crayon/context/ ─> crayon-plan -> crayon-write -> crayon-review
```

- **crayon-onboard** — outside the per-unit loop, run once and then occasionally. Walks the
  repository's own documentation surfaces and cross-reads the product surface, then authors
  the three context artefacts (`doc-style.md`, `glossary.md`, `structure.md`) that later
  ground `crayon-plan`. It writes nothing itself: each artefact reaches the tool through
  `crayon context stage <name> --body-file -`, and `crayon context record` promotes the set
  into `.crayon/context/`, freezes a digest manifest and commits with no `Crayon-Unit`.
  Routes a non-standard source to crayon-fetch.

- **crayon-fetch** — the same artefacts from sources the author declares that live outside
  the repository: a local export, another checkout, a URL, a result the harness already
  holds. Every source is declared before retrieval and recorded with its origin, method,
  revision and preservation status; an unreachable one is reported as failed, never
  substituted. Each artefact is staged with its `--source` locators and recorded through
  the same two verbs.

- **crayon-plan** — grounds itself in the repo's prior art (`.crayon/context/`
  artefacts, read through `crayon context show --json`, and existing docs conventions),
  offers the bootstrap choice once when the context is missing, runs the Socratic
  intake, and ends with the gate act. It writes nothing itself: the plan reaches disk through
  `crayon unit new <id> … --body-file -`, and the gate act through `crayon signoff <id>`.
  Also serves advise-only triage asks ("does this need docs?") with a grounded Triage
  Recommendation, declaring nothing until the TA says go. Routes on the declared
  Diátaxis direction: all four directions → crayon-write.

- **crayon-write** — the sole drafting skill and the only skill that writes files,
  covering all four directions (reference / explanation / tutorial / how-to) in two
  modes. Reference and explanation author the page straight from the declared
  sources; tutorial and how-to walk an evidence-gated step plan and draft from what
  actually ran, each step's verbatim proof recorded via `crayon step`, whose digests
  the tool computes. Either way the page is staged under `.crayon/staging/<id>/draft/`
  and recorded via `crayon draft`.

- **crayon-review** — surfaces the drafted unit for human review through two modes
  (record / review with five-dimension findings), then records the verdict via
  `crayon review`. Accept seals the basis; fix and redraft record the note as
  steering. Never edits the draft.

## Verbs

Transcribed from `docs/contract.md` §6. No skill may invoke a flag that is not here.

| Verb | Key args | Events |
|---|---|---|
| `unit new <id> --intent --audience --title --target [--also-target]… [--source]… [--notes] --body-file -\|F` | | `ledger`, `unit-declared` |
| `unit edit <id> [flags] [--body-file -] [--re-sign]` | | `unit-edited` (+ `signoff`) |
| `unit retire <id> --note` | | `retired` |
| `signoff <id>` | | `signoff` (+2 on adoption) |
| `steer <id> --note\|--note-file - [--origin]` | | `steering` |
| `plan-steps <id> --steps-file -\|F [--keep-evidence --note]` | | `steps-planned` |
| `step <id> <step-id> --steps-seq N --evidence-file F [--output-file F]` | | `step-recorded` |
| `draft <id> <staging file\|dir> [--model --model-origin] [--report F] [--unsteered-reason T]` | | `generation` |
| `edits <id> --note\|--note-file -` | complete basis set; brownfield adoption | `reviewer-edit` |
| `review <id> --verdict accept\|fix\|redraft --note\|--note-file - [--resolves a,b] [--withdraw <seq> "<reason>"]…` | | `review` |
| `resume <id> [--dry-run\|--overwrite\|--adopt --note]` | two-pass | batch completion (+ `reviewer-edit`) |
| `context stage <name> --body-file -\|F [--source]…` | repo-level; tool-owned staging | — |
| `context record [--model --model-origin] [--note]` | repo-level; one commit, no unit | — (manifest) |
| `context show [--json]` | read-only | — |
| `show <id> [--json\|--diff]`, `summary <id> [--json\|--md]`, `verify <id> [--json\|--verbose]`, `version [--json]` | read-only | — |

Every transition emits one local git commit with `Crayon-Unit:` / `Crayon-Phase:`
trailers and explicit pathspecs (never a directory, never the whole repo). The one
repo-level transition, `context record`, commits the same way with `Crayon-Phase:
context-recorded` and no `Crayon-Unit:` — the context belongs to the repository, not
to a unit. The tool never pushes, opens PRs, builds, or publishes.

## Routing

Every `crayon` invocation answers with either a `Next: <token>` response line or a
single-line JSON refusal carrying `error` and `next`. A skill never decides where the
loop goes — it reads the token or the reason and acts on the row below.

This table is authored **here, once**, between the two sentinel comments, and
mirrored byte-identically into each skill's `references/routing.md` (D-13). The
mirrors are what actually ship, because the loading model auto-loads each skill
directory but never this file. When you change a row, change it here and re-copy the
block between the sentinels — `tests/test_skill_text.py` (S-03) asserts the three
copies are equal.

The first block is one row per reason in `docs/contract.md` §5.7's reason table, in
that table's order; the second is one row per `next` token in §5.5's order. A row
describes what the tool already decided. It never restates, softens or duplicates a
precondition — the preconditions live in §5.7 and nowhere else.

<!-- routing-table:begin -->
| reason or next token | what the skill does | verb to call |
|---|---|---|
| `no_signoff` | The unit carries no current signoff, so nothing may be recorded against it. Read the plan back to the author, get an explicit go-ahead, and record the gate act. | `crayon signoff <id>` |
| `plan_stale` | The plan moved after the signoff that authorised it. Read the current plan back to the author and re-sign on their explicit go-ahead. | `crayon signoff <id>`, or `crayon unit edit <id> [flags] --re-sign` |
| `page_drift` | A basis page on disk no longer holds the bytes crayon recorded. Name the paths from the refusal's `detail` and record them onto the record before anything else. | `crayon edits <id> --note "…"` |
| `target_exists` | A signed target already holds bytes crayon never recorded. Same answer as drift — adopt the file as the basis rather than drafting over it unseen. | `crayon edits <id> --note "…"` |
| `target_missing` | An accept was asked for while a basis page is absent or unlisted. Record the author's restoration request; the next draft restores the page. | `crayon steer <id> --note "…"` |
| `generation_stale` | The plan was amended after the last generation, so that draft no longer answers the current plan. Draft again — walk the steps first if the unit is actionable. | `crayon draft <id> <staging file\|dir>` |
| `unapplied_steering` | Accept was asked for with steering still pending; `detail` lists the seqs. Put each one to the reviewer and re-run accept resolving or withdrawing every seq. | `crayon review <id> --verdict accept --note "…" --resolves a,b [--withdraw <seq> "<reason>"]…` |
| `unsteered` | A second generation was asked for with no steering between it and the last one. Record what the author wants changed, or re-run the draft stating why it is unsteered. | `crayon steer <id> --note "…"` then `crayon draft`, or `crayon draft <id> <staging file\|dir> --unsteered-reason "…"` |
| `no_generation` | A verdict was asked for on a unit that has no draft yet. Draft first. | `crayon draft <id> <staging file\|dir>` |
| `target_claimed` | Name the holding unit from the refusal's `detail`, tell the author the target is still listed in that unit's current signoff, and offer to release it. Retire only on an explicit yes — it is another unit's record. Then retry the declaration unchanged. | `crayon unit retire <holder> --note "…"`, then re-run the refused command |
| `retired` | The unit is retired and every mutating verb refuses on it. STOP — a retired unit is never reopened; offer a fresh declaration for the same target instead. | `crayon unit new <new-id> …` |
| `bad_target` | The target, identifier or context artefact name breaks the input rules; the refusal names the offending value. Read it back to the author and re-run with a corrected value — a docs-relative `.md` or `.rst` path for a target, one of the five context artefact names for `context stage`. | re-run the refused command with the corrected value |
| `bad_write_path` | A write destination resolved outside the repo. STOP and report the path from `detail` verbatim — this is a repo-layout problem, not something to retry. | none — report and stop |
| `bad_draft_path` | The staging path is not inside the unit's own draft directory, or a directory does not hold exactly the signed targets. Re-stage and re-run. | `crayon draft <id> .crayon/staging/<id>/draft/…` |
| `bad_resolution` | `--resolves` / `--withdraw` named a seq that is not pending, repeated one, crossed the two sets, or left a withdrawal without a reason. Read the pending seqs back and re-run accept with a corrected set. | `crayon review <id> --verdict accept --note "…" --resolves a,b [--withdraw <seq> "<reason>"]…` |
| `unit_invalid` | `unit.md` is not the declared shape; the refusal names the line and the flag that owns that field. Fix the field through that flag, never by hand-editing around the tool. | `crayon unit edit <id> [flags] [--body-file -]` |
| `unit_exists` | That id is already declared. Show the existing unit and continue on it, or agree a new id with the author. | `crayon show <id>` |
| `unit_not_found` | No unit with that id exists. Ask the author for the right id rather than guessing, or declare it. | `crayon show <id>` on the corrected id, or `crayon unit new <id> …` |
| `step_unknown` | The id given is not in the plan named by `--steps-seq`; the refusal lists the ids that plan does name. Read those back and re-run with one of them — never invent a step the plan does not carry. | `crayon show <id> --json`, then `crayon step <id> <step-id> --steps-seq N --evidence-file F --output-file F` |
| `not_actionable` | Steps were planned or recorded on a unit whose intent is neither tutorial nor how-to. STOP walking — reference and explanation are authored straight from the declared sources. | `crayon draft <id> <staging file\|dir>` |
| `note_required` | The note was empty, carried a carriage return, or exceeded the cap. Ask the author for the note again and re-run the same verb with it. | re-run the refused command with `--note "…"` or `--note-file -` |
| `git_identity_missing` | git has no author identity, so no commit can be made. STOP and tell the author to configure their own git identity — the skill never sets it for them. | none — report and stop |
| `not_a_repo` | The working directory is not inside a git repository. STOP and say so; crayon records into the repo it is run from. | none — report and stop |
| `legacy_unit` | The unit is a v1.x record this tool does not read. STOP and show the archive hint from the refusal verbatim; declare a fresh unit if the author wants the page redone. | `crayon unit new <new-id> …` |
| `identical_draft` | Nothing changed — every signed target already holds the staging bytes. Report the existing seq and commit from the payload and act on the `next` it carries. | act on the payload's `next` |
| `already_signed` | The plan is already signed at that hash. Report the existing seq and commit from the payload and act on the `next` it carries. | act on the payload's `next` |
| `already_accepted` | The unit is already accepted on this basis with no history since. Never record a second accept — report the existing seq and commit. | act on the payload's `next` |
| `already_recorded` | This step evidence is already on the record, field for field. Report the existing seq and commit and move to the next step. | `crayon step <id> <next-step-id> --steps-seq N --evidence-file F --output-file F` |
| `already_retired` | The unit was already retired. Report the existing seq and commit; there is nothing further to record on it. | none — report and stop |
| `no_edits` | No basis file changed and nothing is adoptable, so there is nothing to record. Say so and act on the `next` the payload carries. | act on the payload's `next` |
| `noop_unchanged` | The edit left the frontmatter and the body unchanged, or every staged context artefact already holds its recorded bytes (the staged copies are discarded). Say so and act on the `next` the payload carries. | act on the payload's `next` |
| `nothing_to_resume` | There is no tail and no pending batch — the record is whole. Say so and act on the `next` the payload carries. | act on the payload's `next` |
| `steps_unresolved` | An actionable unit was drafted with steps still unresolved; the refusal lists them. Run each one and record its evidence before drafting. | `crayon step <id> <step-id> --steps-seq N --evidence-file F --output-file F` |
| `steps_missing` | The unit is actionable and has no step plan at all. Agree the steps with the author, record the plan, then walk it. | `crayon plan-steps <id> --steps-file -` |
| `evidence_stale` | The plan this evidence names was **superseded** by a later `plan-steps`; the refusal gives both seqs. The evidence is not wrong, it answers an instruction that has moved — re-run the command and record it against the current seq. | `crayon step <id> <step-id> --steps-seq N --evidence-file F --output-file F` |
| `evidence_incomplete` | The evidence JSON is missing a required field, or a `pass` / `fail` / `deviated` step arrived without `--output-file`. Re-run the command capturing its output to a file and record that file — never type a digest. | `crayon step <id> <step-id> --steps-seq N --evidence-file F --output-file F` |
| `evidence_mismatch` | The evidence JSON's `mode` is not the `mode` the plan declares for this step; the refusal names both. Record the step in the declared mode, or re-plan the step if the mode itself was wrong. Re-running the command unchanged cannot clear this — the mode is a field of the evidence, not of the run. | `crayon step <id> <step-id> --steps-seq N --evidence-file F --output-file F` with the declared `mode`, or `crayon plan-steps <id> --steps-file -` |
| `busy` | Another crayon run holds the staging lock. STOP, wait for it to finish, then re-run the same command unchanged. | re-run the refused command unchanged |
| `git_busy` | A git process is mid-write in this repo. STOP, wait for it to finish, then re-run the same command unchanged. | re-run the refused command unchanged |
| `ledger_corrupt` | The record does not verify. STOP and show the author the full verify report; never hand-edit the ledger. | `crayon verify <id> --verbose` |
| `ledger_version_unsupported` | The record declares a contract number this tool does not implement. STOP and report both numbers from the refusal; never hand-edit the ledger. | `crayon version --json` |
| `unit_id_mismatch` | The record's header names a different unit than the directory holding it. STOP and report both ids; never hand-edit the ledger. | none — report and stop |
| `uncommitted_tail` | An interrupted run left uncommitted lines. Show the author what a resume would do; with `unexpected` files, use the `resume_ambiguous` row. Otherwise complete it. | `crayon resume <id> --dry-run`, then `crayon resume <id>` only with no `unexpected` files |
| `ledger_diverged` | The committed prefix was rewritten in git history. STOP and show the git recipe from the refusal verbatim. | none — report and stop |
| `resume_ambiguous` | Files on disk differ from what the interrupted run intended; the printed per-file diff shows each one. Show that stdout verbatim and offer the author exactly two choices — discard the on-disk bytes, or keep them as a recorded reviewer edit. Recording a new reviewer edit is available **only when the batch's last event is a generation or a reviewer edit that is not itself an adoption, a file is `unexpected`, and every unexpected file's current bytes are still on disk**: this refusal is raised on any batch whose placed files were rewritten, including the `signoff`, `unit edit`, `plan-steps`, `step`, `review`, `edits` and `unit retire` batches that write `unit.md`, and on those `--adopt` refuses `adopt_unsupported`. When recording a new adoption, a deleted file also refuses `adopt_unsupported`: there are no current bytes to adopt. Offer the discard alone there. A batch whose last event is already an adoption (`hook: true`) has a different keep path: `crayon resume <id> --adopt` retains the on-disk bytes while completing the existing batch; it appends no event and records no note. `crayon resume <id> --overwrite` restores that adoption's saved bytes instead. Bare `crayon resume <id>` is available only with no `unexpected` files. After completion, follow the emitted route: if the bytes still differ from the recorded adoption, `record_edits` calls for `crayon edits <id> --note "…"`; a hook may have restored them during the commit. Both choices retry the transition, so remove what is refusing the transition before running either one. | `crayon resume <id> --overwrite`; only when the batch ends in a generation or reviewer edit that is not itself an adoption and every unexpected file's rewritten bytes are still on disk, `crayon resume <id> --adopt --note "…"`; for an already-adopted batch, `crayon resume <id> --adopt` retains bytes without another event or note |
| `recovery_unsupported` | Show the printed findings verbatim, then branch on `detail`. **`detail: commit_rejected` and `detail: stage_rejected`** — the batch IS appended to the record and the files ARE placed; the transition failed twice. Show the printed git output: that is what is blocking it, and removing it then resuming once more is the escape that always works. The two details name different causes and must not be read aloud as the same one: on `commit_rejected` git ran the commit and something refused it, so the answer is the repository's commit hooks; on `stage_rejected` the commit was never attempted and no hook ran, so it is `git status` and the index — an unstageable pathspec, an index that will not lock, a read-only `.git`. `--adopt` is the escape ONLY when the hook REWROTE the placed bytes of a generation or a reviewer edit that is not itself an adoption and every unexpected file's current bytes are still on disk; deleted files also refuse `adopt_unsupported` (use `--overwrite` after removing any remaining blocker); for an already-adopted batch, use the `resume_ambiguous` row to choose retained or saved bytes; on other ineligible batches it refuses `adopt_unsupported`, and with the bytes unchanged it is a plain resume that will be refused again. Never offer it without that condition. **Every other detail** — `no_material`, `material_invalid`, `event_invalid`, `tail_unknown` — is stage a's, and there nothing was written: offer no recipe of your own, restore nothing from HEAD, and never commit the tail. | on `commit_rejected` or `stage_rejected`, remove what is refusing the transition then `crayon resume <id>` only with no `unexpected` files (otherwise use the `resume_ambiguous` row); only when a hook rewrote a generation's or a reviewer edit's placed bytes, that edit is not itself an adoption, and every unexpected file's current bytes are still on disk, `crayon resume <id> --adopt --note "…"`; on every other detail, none — report and stop |
| `adopt_unsupported` | The tool raises this from **two** places and `detail` says which. **`detail: the batch's last event is a <kind>`** — `--adopt` was asked for on a batch that is neither a generation nor a reviewer edit, so there is no generation to restate; the flag is offerable only when the last event is one of those two, is not itself an adoption, and every unexpected file's rewritten bytes are still on disk. **`detail: <path> is not on disk and has no current bytes to adopt`** — the batch ends in a generation or a reviewer edit, but the path the hook was expected to rewrite is gone (a "generated files must not be committed" hook deletes its target), so there are no current bytes to make durable. Offer to restore the intended bytes with `--overwrite`. If something is still refusing the transition, remove what is refusing the transition first. The hint reports `transition_attempts` as a historical count, not evidence of a current blocker; removing a hook does not reset it. Both raise sites retain the overwrite remedy at every count. | once nothing is refusing the transition, `crayon resume <id> --overwrite` |
| `internal_error` | crayon itself fell over below the verb. This is a defect in the tool, not a diagnosis of the author's record: nothing here has established that anything is wrong with the ledger or the pages. Report the refusal's `detail` verbatim — it names the exception — and re-run the same command unchanged. Hand-edit nothing, and run no recovery verb; `show` is read-only and is the route for that reason. | `crayon show <id>`, then re-run the refused command unchanged |
| `resume` | An interrupted run is waiting. Show the author what a resume would do, then complete it — **unless the refusal carrying this token was `recovery_unsupported` with `detail: commit_rejected` or `detail: stage_rejected`**, in which case a plain resume is the command that just refused; act on that reason's row instead, and note that the `--adopt` it names is conditional: a deleted file refuses `adopt_unsupported`. Both details carry this token and both re-offer the command that produced them; they differ only in what is blocking the transition — a commit hook on `commit_rejected`, the index on `stage_rejected`. | `crayon resume <id> --dry-run`, then `crayon resume <id>` only with no `unexpected` files (otherwise use the `resume_ambiguous` row); on `commit_rejected` or `stage_rejected`, remove what is refusing the transition first, and use `crayon resume <id> --adopt --note "…"` only when a hook rewrote a generation's or a reviewer edit's placed bytes, that edit is not itself an adoption, and every unexpected file's current bytes are still on disk |
| `retired` | The unit is retired. STOP — say so and offer a fresh declaration for the same target. | `crayon unit new <new-id> …` |
| `sign_off` | Read the plan back to the author and record the gate act on their explicit go-ahead. | `crayon signoff <id>` |
| `re_sign` | The plan moved after its signoff. Read the current plan back and re-sign on the author's explicit go-ahead. | `crayon signoff <id>`, or `crayon unit edit <id> [flags] --re-sign` |
| `record_edits` | Basis bytes on disk are not the recorded ones. Name the paths and record them before drafting or reviewing. | `crayon edits <id> --note "…"` |
| `walk` | The unit is actionable with unresolved steps. Run each step, capture its output to a file, and record the evidence the tool hashes. | `crayon step <id> <step-id> --steps-seq N --evidence-file F --output-file F` |
| `draft` | Author the page, stage it under the unit's own draft directory, and record it. | `crayon draft <id> <staging file\|dir>` |
| `publish` | The unit is accepted and its pages are current. STOP — crayon stops here; the author owns the PR, the build and the publish. | none — report and stop |
| `steer` | Record the author's request on the record before drafting again. | `crayon steer <id> --note "…"` |
| `review` | A generation or a reviewer edit is the tip. Surface it for review and record the verdict the reviewer gives. | `crayon review <id> --verdict accept\|fix\|redraft --note "…"` |
| `record` | Context artefacts are staged and not yet recorded. Record them — one commit, no unit — and echo the tool's line. | `crayon context record [--model … --model-origin …] [--note "…"]` |
| `onboard` | No context is recorded yet: at least one of `doc-style.md`, `glossary.md`, `structure.md` is absent. STOP and offer the author the bootstrap choice — supply the files, run `/crayon-onboard`, or ground this intake ephemerally; never author `.crayon/context/` yourself. | none — route to `/crayon-onboard` (a skill), or continue on the author's choice |
| `plan` | The context artefacts are recorded and current. STOP — context is done; the next act is a unit declaration. | none — route to `/crayon-plan` (a skill) |
<!-- routing-table:end -->

## Installation

`install.sh` at the root of the checkout installs the tool and the five skills, project-scoped
into a docs repository's `.agents/skills/` or globally into `~/.agents/skills/`, and verifies the
result; [`docs/install.md`](../docs/install.md) explains every choice and the manual equivalent.
By hand, the skills are one copy:

```bash
CRAYON=/path/to/crayon
mkdir -p .agents/skills && cp -r "$CRAYON"/skills/crayon-* .agents/skills
```

`cp -r skills/crayon-*` copies the five skill directories and nothing else: this file
is **not** installed. That is why each skill carries its own
`references/routing.md` — the routing table has to travel inside the skill directory
to be readable at runtime.

## Compatibility

| Number | Value |
|---|---|
| `contract` | `1` |
| `min_tool` | `0.2.0` |

Every skill declares both in its frontmatter as `metadata.crayon_contract: 1` and
`metadata.crayon_min_tool: "0.2.0"`, and opens by reading `crayon version --json`, which
answers `{"tool","contract"}`. The two numbers are compared as **literal strings** —
never parsed or rounded as versions.

A skill stops for exactly two reasons: the tool answers anything other than
`contract 1`, or its `tool` version is older than `min_tool 0.2.0` (`0.1.9` is older). Anything else is a
routing row above, not a stop.

## Hooks

A repository's own commit hooks may rewrite the bytes crayon just recorded. The tool
detects both shapes and names the answer; the skill does not improvise one.

- A hook that rewrites a target and **rejects** the commit ends in `resume_ambiguous`.
  The answer is `--adopt`: the author keeps the hook's bytes, recorded as a reviewer
  edit whose note says a hook changed them.
- A hook that rewrites a target and **succeeds** ends in the post-commit warning
  `hook changed <path> after recording`, followed by the routed `Next:`. The answer is
  `edits`.

In both cases the recorded note says a hook changed the bytes and the author retained
them. **A formatter is not a reviewer** — it has no verdict and its rewrite is never
presented as one. Restoring the intended bytes instead means a recorded `steer` and a
re-draft from staging, which the hook will simply rewrite again; with a formatting
hook on target paths the supported behaviour is to adopt.

## Vocabulary

- **sealed** — a unit whose latest review is an **accept** with no history after it.
  Derived by reading the record, never stored as a flag.
- **record** (the ledger) — the hash-chained JSONL audit trail at
  `.crayon/units/<id>/ledger.jsonl`, one canonical line per event, each line's `prev`
  the digest of the previous line's bytes. Append-only: **never hand-edit the ledger**,
  because editing one line invalidates every `prev` after it.
- **gate** — the signoff act recorded by `crayon signoff`. Every mutating verb checks it
  inline before recording anything.
- **basis** — the set of files a generation or an accept is recorded against.

## Licensing

The skills under `skills/` are licensed under **Apache-2.0** (see `LICENSE`).
The tool at the repository root is licensed under **LGPL-3.0-only** (see the root
`LICENSE`).
