# dogen

**dogen** drafts review-ready, **Sphinx-publishable** documentation (MyST Markdown or
reStructuredText, Diátaxis-structured) from sources you point it at, with you in the loop, and
stops at one traceable local commit. You drive it from your coding agent through three skills;
one stdlib-only executable underneath enforces the guarantees — no substantial draft without
your recorded signoff, and a hash-chained record of every step.

## Quickstart (5 minutes)

**1. Install.** One script; Enter takes every default (tool in `~/.local/bin`, skills into the
docs repository you are in, `.dogen/staging/` ignored, install verified).

```bash
git clone https://github.com/akcano/dogen-mvp-1 ~/src/dogen
cd /path/to/your-docs-repo
~/src/dogen/install.sh
```

Every choice the script makes, and the manual equivalent, is in
[`docs/install.md`](docs/install.md).

**2. Plan.** Open your agent in the docs repository and start the first skill — `/dogen-plan` in
Claude Code, or "use the dogen-plan skill to document …" elsewhere. Tell it what page you need.
It asks one question at a time about the audience, the sources and the shape, reads the plan
back to you, and records your **signoff** when you say go.

**3. Write.** `/dogen-write`. It drafts the page from the plan and its sources — or, for a
tutorial or how-to, by actually running the steps and writing from what happened — and records
the draft as a local commit.

**4. Review.** `/dogen-review`. Read the draft; say **accept**, or say what to **fix**, or ask
for a **redraft**. Fixes and redrafts go back to step 3 with your words on the record.

You now have the page under `docs/`, one local commit per step, and `dogen summary <id> --md`
gives you paste-ready pull-request text. dogen never pushes; you own the PR.

## How you use it

You talk to your agent. The agent runs the skills; the skills call the tool. You never type a
`dogen` command yourself unless you want to.

1. **`dogen-plan`** declares one page: what it is, who it is for, where the facts come from, and
   where it lands. It ends with your signoff, which is the gate — nothing substantial can be
   recorded against the page until you have given it.
2. **`dogen-write`** produces the draft. It is the only skill allowed to write files.
3. **`dogen-review`** records your verdict. Accept seals the page; fix and redraft record your
   steering and send it back to the writer.

If you close the conversation at any point, start the same skill again: it reads the record,
tells you where you are, and continues. If something is refused, the skill says why and what it
will do next; you are never asked to repair the record by hand.

## Keep dogen on its own branch

dogen commits every transition, with the ledger under `.dogen/` alongside the page. That history
is provenance, not product, so keep it off your main line:

- **Work on a dogen branch.** `git switch -c dogen/widget-api main`, and run the skills there.
  Every commit touches only `.dogen/` and `docs/` and carries `Dogen-*` trailers.
- **Do not merge that branch.** Ship the page from a review branch popped off main, one squashed
  commit, the page only:

  ```bash
  dogen summary widget-api --md > /tmp/widget-api-pr.md   # on the dogen branch
  git switch -c docs/widget-api main
  git restore --source dogen/widget-api -- docs/reference/widget-api.md
  git add docs/reference/widget-api.md
  git commit -m "docs: add the Widget API reference"
  ```

  Reviewers see prose and a PR body written from the record, not ledger lines.
- **Keep the dogen branch for investigations.** `dogen show`, `dogen verify` and
  `git log --grep 'Dogen-Unit: widget-api'` replay the whole path — who steered what, which
  sources, which evidence — for as long as the branch exists.
- **Bring main back in with a merge, never a rebase.** `git merge main` on the dogen branch.
  Rewriting its commits is what the record calls history squashed: `verify` warns, and a
  dropped ledger line is refused as `ledger_diverged`. After the merge the page on main may
  differ from what the record last saw (review edits); `dogen show` reports that drift and the
  next skill records it with `dogen edits` as the new basis.
- **One branch per page or one long-lived `dogen` branch?** One per page is the default, and it
  keeps each investigation self-contained. A single long-lived branch works when one author owns
  the whole docs set and wants one place to look.

## What dogen will not do

- It does **not** push, open or review pull requests, build, or publish. It drafts and stops at
  a local commit.
- It does **not** draft without you: steering is mandatory and recorded, and a substantial draft
  is refused until your signoff is on record.
- It does **not** label the output. There is no "AI-generated" disclaimer, because the humans who
  review and merge it stand behind what ships. Provenance is internal observability.

## Glossary

- **unit** — one documentation unit: a declared intent, audience, title, source list and one or
  more target pages, recorded in `.dogen/units/<id>/unit.md`.
- **intent** — the page's Diátaxis direction: `reference`, `explanation`, `tutorial` or
  `how-to`. Tutorials and how-tos are *actionable*: they are drafted from a step walk.
- **target** — where the page lands, as a path relative to `docs/`; the extension is the format
  (`.md` MyST, `.rst` reStructuredText).
- **signoff** — your recorded go-ahead on the plan. It freezes the plan's hash; a plan that
  changes afterwards needs a new signoff.
- **steering** — anything you ask for in your own words, recorded before the next draft. A
  second draft with no steering since the last one is refused.
- **step walk** — for actionable units, each planned step is run, its output captured and its
  digests recorded, before a draft may be recorded.
- **generation** — one recorded draft: the write of every target page and the record of it.
- **basis** — the set of pages, with their digests, that the record currently stands behind.
  Bytes on disk that differ are **drift**; drift is reported and adopted, never overwritten.
- **sealed** — a unit whose latest review is an accept.
- **ledger** — the record of truth at `.dogen/units/<id>/ledger.jsonl`: hash-chained JSON lines,
  append-only. State is derived by reading it; never edit it by hand.
- **staging** — `.dogen/staging/`, the writer's working space; ignored by git.
- **context files** — `.dogen/context/`: your style guide, glossary and structure notes, read by
  every skill. See [`docs/install.md`](docs/install.md#add-context-files-recommended).

### The verbs, if you ever need them

One row per subcommand of `dogen`. The skills call these; the normative definition of each
verb's preconditions, no-ops and gates is [`docs/contract.md`](docs/contract.md) §5.7 and §6.

<!-- VERBS:BEGIN -->

| Verb | What it records | Key args |
|---|---|---|
| `unit` | Declares (`new`), amends (`edit`) or retires (`retire`) a unit. `edit --re-sign` amends and re-signs in one act; `retire` releases the unit's claim on its targets. | `new <id> --intent --audience --title --target [--also-target]… [--source]… [--notes] --body-file -\|F` · `edit <id> [flags] [--body-file -] [--re-sign]` · `retire <id> --note` |
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
| `verify` | Read-only: contract §5.9's V1–V19 over the whole record. | `<id> [--json]` |
| `version` | Read-only: the tool version and the contract number. | `[--json]` |

<!-- VERBS:END -->

There is no forcing flag anywhere on this surface. Re-signing an amended plan is
`dogen unit edit <id> … --re-sign`, which records the amendment and the new signoff together.

### Exit codes

A non-zero exit prints **exactly one JSON line** with the five keys `error`, `unit`, `detail`,
`hint` and `next` — on stderr, or on stdout under `--json`. Branch on `error`, not on the exit
code, which several reasons share.

<!-- REASONS:BEGIN -->

| Exit | Meaning | Reasons |
|---|---|---|
| `0` | success | |
| `1` | gate — a precondition of the transition is not met | `no_signoff`, `plan_stale`, `page_drift`, `target_exists`, `target_missing`, `generation_stale`, `unapplied_steering`, `unsteered`, `no_generation`, `target_claimed`, `retired` |
| `2` | bad input — unknown unit or step, missing file, path traversal, unknown flag | `bad_target`, `bad_write_path`, `bad_draft_path`, `bad_resolution`, `unit_invalid`, `unit_exists`, `unit_not_found`, `step_unknown`, `not_actionable`, `note_required`, `git_identity_missing`, `not_a_repo`, `legacy_unit` |
| `3` | no-op — the request is already on the record; nothing to do | `identical_draft`, `already_signed`, `already_accepted`, `already_recorded`, `already_retired`, `no_edits`, `noop_unchanged`, `nothing_to_resume` |
| `4` | evidence — missing, unresolved, stale or mismatched step evidence | `steps_unresolved`, `steps_missing`, `evidence_stale`, `evidence_incomplete`, `evidence_mismatch` |
| `5` | busy — another dogen run or another git process holds a lock | `busy`, `git_busy` |
| `6` | ledger and recovery — the record needs attention before the tool may write | `ledger_corrupt`, `ledger_version_unsupported`, `unit_id_mismatch`, `uncommitted_tail`, `ledger_diverged`, `resume_ambiguous`, `recovery_unsupported`, `adopt_unsupported`, `internal_error` |

<!-- REASONS:END -->

The authoritative list is the tool's own `REASONS` table and
[`docs/contract.md`](docs/contract.md) §5.7; the table above is checked against both.

## Further reading

- [`docs/install.md`](docs/install.md) — every install choice, the manual install, context files.
- [`docs/upgrade.md`](docs/upgrade.md) — upgrading the tool, the skills and existing records.
- [`docs/compatibility.md`](docs/compatibility.md) — the contract number and the minimum tool.
- [`docs/hooks.md`](docs/hooks.md) — what happens when a formatting hook rewrites a page.
- [`docs/contract.md`](docs/contract.md) — the normative specification, frozen at `contract-v1`.
- [`skills/README.md`](skills/README.md) — the skill family contract and the routing table.
- [`docs/development.md`](docs/development.md) — tooling, testing and verification for
  contributors; [`docs/shellcheck.md`](docs/shellcheck.md) — the shell lint policy.
- [`CHANGELOG.md`](CHANGELOG.md) — the release record.

## Licensing

The tool is licensed under **LGPL-3.0-only** (see [`LICENSE`](LICENSE)). The portable skills
under [`skills/`](skills/) are licensed separately under **Apache-2.0** (see
[`skills/LICENSE`](skills/LICENSE)).
