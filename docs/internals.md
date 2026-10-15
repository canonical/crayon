# Under the hood

<!-- provenance: moved from README.md (Keep crayon on its own branch, Glossary, The verbs, Exit codes, Repository layout) -->

The five skills record every step through one executable, `crayon`. You never need to run it
yourself. This page is for when you want to look underneath: the terms the record uses, the
commands the skills run, the exit codes, and how the record lives in git. The normative
statement of all of it is [[contract]].

## Glossary

- **unit**: one documentation unit. A declared intent, audience, title, source list and one or
  more target pages, recorded in `.crayon/units/<id>/unit.md`.
- **intent**: the page's Diátaxis direction: `reference`, `explanation`, `tutorial` or
  `how-to`. Tutorials and how-tos are *actionable*: they are drafted from a step walk.
- **target**: where the page lands, as a path relative to `docs/`. The extension is the format:
  `.md` is MyST, `.rst` is reStructuredText.
- **signoff**: your recorded approval of the plan. It freezes the plan's hash. A plan that
  changes afterwards needs a new signoff.
- **steering**: anything you ask for in your own words, recorded before the next draft. A
  second draft with no steering since the last one is refused.
- **step walk**: for actionable units, each planned step is run, its output captured and its
  digests recorded before a draft can be recorded.
- **generation**: one recorded draft: the write of every target page and the record of it.
- **basis**: the set of pages, with their digests, that the record currently stands behind.
  Bytes on disk that differ are **drift**. Drift is reported and adopted, never overwritten.
- **sealed**: a unit whose latest review is an accept.
- **ledger**: the record of truth at `.crayon/units/<id>/ledger.jsonl`. Hash-chained JSON lines,
  append-only. State is derived by reading it. Never edit it by hand.
- **staging**: `.crayon/staging/`, the writer's working space. git ignores it.
- **context files**: `.crayon/context/`: `doc-style.md`, `glossary.md`, `structure.md`, and the
  optional `code-to-docs-map.md` and `doc-gaps.md`. The plan and write skills read them. They
  are recorded through `crayon context stage` and `crayon context record`, which freeze their
  digests in `manifest.json`. See [[context]].

## The verbs

One row per subcommand of `crayon`. The skills call these. The normative definition of each
verb's preconditions, no-ops and gates is [[contract]] §5.7 and §6.

<!-- VERBS:BEGIN -->

| Verb | What it records | Key args |
|---|---|---|
| `unit` | Declares (`new`), amends (`edit`) or retires (`retire`) a unit. `edit --re-sign` amends and re-signs in one act; `retire` releases the unit's claim on its targets. | `new <id> --intent --audience --title --target [--also-target]… [--source]… [--notes] --body-file -\|F` · `edit <id> [flags] [--body-file -] [--re-sign]` · `retire <id> --note` |
| `context` | The repository's context artefacts, outside any unit: `stage` hands the tool one artefact's text (a skill holds no write tool), `record` promotes the staged set into `.crayon/context/`, freezes a manifest of tool-computed digests and commits, `show` reports what is present, staged, unrecorded or drifted. No ledger event; one commit with no `Crayon-Unit`. | `stage <name> --body-file -\|F [--source]…` · `record [--model --model-origin] [--note]` · `show [--json]` |
| `signoff` | The human gate. Freezes `sha256(unit.md)` as the plan hash the later verbs are checked against. | `<id>` |
| `steer` | One steering request, in the author's words. Without one since the last generation, `draft` refuses `unsteered`. | `<id> --note\|--note-file - [--origin]` |
| `plan-steps` | The step plan of an actionable unit (`tutorial` or `how-to`). Supersedes any earlier plan. | `<id> --steps-file -\|F [--keep-evidence --note]` |
| `step` | One step's evidence: output bytes, exit code and digests, against a named step of the current plan. | `<id> <step-id> --steps-seq N --evidence-file F [--output-file F]` |
| `draft` | A generation, and the write of every signed target. Refuses without a current signoff, on page drift, or with unresolved steps. | `<id> <staging file\|dir> [--model --model-origin] [--report F] [--unsteered-reason T]` |
| `edits` | A hand edit or a brownfield adoption, recorded as the **complete** basis set. | `<id> --note\|--note-file -` |
| `review` | A verdict, and the disposition of every pending request. `accept` seals the page digests. | `<id> --verdict accept\|fix\|redraft --note\|--note-file - [--resolves a,b] [--withdraw <seq> "<reason>"]…` |
| `resume` | Completes an interrupted transition in two passes: classify, then write. `--dry-run` writes nothing. | `<id> [--dry-run\|--overwrite\|--adopt --note]` |
| `show` | Read-only: the derived state, per-path drift, pending requests, step tallies and `Next:`. | `<id> [--json\|--diff]` |
| `summary` | Read-only: the unit for a human reviewer. `--md` is paste-ready pull-request text. | `<id> [--json\|--md]` |
| `verify` | Read-only: contract §5.9's V1–V19 over the whole record. Plain by default; `--verbose` prints the full report. | `<id> [--json\|--verbose]` |
| `version` | Read-only: the tool version and the contract number. | `[--json]` |

<!-- VERBS:END -->

There is no forcing flag anywhere on this surface. Re-signing an amended plan is
`crayon unit edit <id> … --re-sign`, which records the amendment and the new signoff together.

## Exit codes

A non-zero exit prints **exactly one JSON line** with the five keys `error`, `unit`, `detail`,
`hint` and `next`: on stderr, or on stdout under `--json`. Branch on `error`, not on the exit
code, which several reasons share.

<!-- REASONS:BEGIN -->

| Exit | Meaning | Reasons |
|---|---|---|
| `0` | success | |
| `1` | gate — a precondition of the transition is not met | `no_signoff`, `plan_stale`, `page_drift`, `target_exists`, `target_missing`, `generation_stale`, `unapplied_steering`, `unsteered`, `no_generation`, `target_claimed`, `retired` |
| `2` | bad input — unknown unit or step, missing file, path traversal, unknown flag | `bad_target`, `bad_write_path`, `bad_draft_path`, `bad_resolution`, `unit_invalid`, `unit_exists`, `unit_not_found`, `step_unknown`, `not_actionable`, `note_required`, `git_identity_missing`, `not_a_repo`, `legacy_unit` |
| `3` | no-op — the request is already on the record; nothing to do | `identical_draft`, `already_signed`, `already_accepted`, `already_recorded`, `already_retired`, `no_edits`, `noop_unchanged`, `nothing_to_resume` |
| `4` | evidence — missing, unresolved, stale or mismatched step evidence | `steps_unresolved`, `steps_missing`, `evidence_stale`, `evidence_incomplete`, `evidence_mismatch` |
| `5` | busy — another crayon run or another git process holds a lock | `busy`, `git_busy` |
| `6` | ledger and recovery — the record needs attention before the tool may write | `ledger_corrupt`, `ledger_version_unsupported`, `unit_id_mismatch`, `uncommitted_tail`, `ledger_diverged`, `resume_ambiguous`, `recovery_unsupported`, `adopt_unsupported`, `internal_error` |

<!-- REASONS:END -->

The authoritative list is the tool's own `REASONS` table and [[contract]] §5.7. The table above
is checked against both by `tests/check_docs.py`.

## Branches and the record

crayon commits every transition, with the ledger under `.crayon/` beside the page. That history
is provenance, not product, so keep it off your main line:

- **Work on a crayon branch.** Create it from main and run the skills there. Every crayon commit
  touches only `.crayon/` and `docs/` and carries `Crayon-*` trailers.
- **Do not merge that branch.** Ship the page from a review branch made from main: one commit,
  the page only. Set the three names first. `UNIT` is the id the unit got in `/crayon-plan`.

  ```bash
  UNIT=my-page                      # the unit id
  PAGE=docs/reference/my-page.md    # the page the unit wrote
  CRAYON_BRANCH=crayon/my-page      # the branch the skills ran on

  crayon summary "$UNIT" --md > "/tmp/$UNIT-pr.md"   # on the crayon branch: the PR text
  git switch -c "docs/$UNIT" main
  git restore --source "$CRAYON_BRANCH" -- "$PAGE"
  git add "$PAGE"
  git commit -m "docs: add $PAGE"
  ```

  Reviewers see prose and a PR body written from the record, not ledger lines.
- **Keep the crayon branch for investigations.** `crayon show "$UNIT"`, `crayon verify "$UNIT"` and
  `git log --grep "Crayon-Unit: $UNIT"` replay the whole path (who steered what, which sources,
  which evidence) for as long as the branch exists.
- **Bring main back in with a merge, never a rebase.** Run `git merge main` on the crayon branch.
  Rewriting its commits is what the record calls history squashed: `verify` warns, and a
  dropped ledger line is refused as `ledger_diverged`. After the merge, the page on main may
  differ from what the record last saw (review edits). `crayon show` reports that drift, and the
  next skill records it with `crayon edits` as the new basis.
- **One branch per page, or one long-lived `crayon` branch?** One per page is the default, and
  it keeps each investigation self-contained. A single long-lived branch works when one author
  owns the whole docs set and wants one place to look.

## Repository layout

- `crayon.py`: the tool, one stdlib-only Python file, installed on your `PATH` as `crayon`.
- `install.sh`: the installer.
- `skills/`: the five Agent Skills your agent runs, and their family contract.
- `docs/`: the wiki: the normative contract and the guides.
- `AGENTS.md`: the guide a coding agent working *on* crayon reads first.
- `scripts/`: stdlib lints that gate the skills, the planning tree and the wiki.
- `tests/`: the test suites and checkers. `validation/`: the evidence kit and the model evals.
  Both are described in [[development]].
- `CHANGELOG.md`, `LICENSE` (LGPL-3.0-only for the tool; `skills/LICENSE` is Apache-2.0).

Related: [[contract]], [[architecture]], [[context]], [[development]].
