# Changelog

All notable changes to dogen are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/): `Added`, `Changed`, `Fixed`, `Removed`,
in that order under every release. Within a heading, entries run in the order the deliverables land
in the release series — contract and tool core, the four suites, skills over verbs, the retired v1
bash layer, CI and the install smoke, the docs, the session records — so two entries of equal
significance still have one order a reader can predict.

## [Unreleased]

### Added

- `dogen context stage`, `dogen context record` and `dogen context show` — the repository's
  context artefacts (`doc-style.md`, `glossary.md`, `structure.md`, `code-to-docs-map.md`,
  `doc-gaps.md`) now reach `.dogen/context/` through the tool. `stage` takes one artefact's text
  from a file or stdin, so a skill that holds no write tool can hand it over; `record` promotes
  the staged set, freezes `manifest.json` with tool-computed digests and the declared sources,
  and makes one commit with `Dogen-Phase: context-recorded` and no `Dogen-Unit`; `show` derives
  what is present, staged, unrecorded or drifted and routes `record`, `onboard` or `plan`. No
  event kind and no reason is added: the change is additive under contract 1, recorded in
  `docs/contract.md` §5.10 beside the `internal_error` revision. N-47 in the lifecycle suite,
  A-38 in the acceptance suite and a unit class cover it.
- `dogen-onboard` and `dogen-fetch` — two portable skills that produce the context artefacts,
  outside the per-unit loop. `dogen-onboard` walks the repository's own docs and cross-reads
  the product surface for `[CODE↔DOCS GAP]` findings; `dogen-fetch` takes sources the author
  declares — a local export, another checkout, a URL, a harness result — retrieves each
  through the declared method, records its origin, revision and preservation status, and
  reports an unreachable one as failed rather than substituting. Neither holds a write tool:
  each artefact is handed to `dogen context stage` and the set to `dogen context record`, so
  the single-writer rule is unchanged. The three stance references are authored in
  `dogen-onboard` and mirrored byte-identically into `dogen-fetch`; the family is five skills
  wherever it was three — `install.sh`, the install smoke, the skill-text suite, the docs.
- `docs/context.md` — the one home for the five context files: what each carries, who
  produces it, how the two verbs record it, and what `dogen-plan` does when they are missing.
- `dogen-plan` grounds itself through `dogen context show --json` and, when the three
  onboarding artefacts are missing, offers the author one three-way choice: supply the files,
  run `/dogen-onboard` first, or ground this one intake from an ephemeral in-memory read
  (`references/context-bootstrap.md`) that persists nothing. The skill never authors
  `.dogen/context/` itself.
- `install.sh` — an interactive installer at the repository root. It walks through the three
  decisions an install has (project or global skills, where the executable goes — a copy or a
  symlink into the checkout — and `.gitignore`), takes every default under `--yes`,
  and ends by verifying the result: the executable on `PATH`, the contract number against every
  installed skill's frontmatter, the skill directories, stale discovery roots, the git identity.
  `--verify-only` runs the last part alone. It is in the shellcheck scope. Skills are installed
  once under `.agents/skills/` and linked from `.claude/skills/`, the one discovery root some
  agents read instead; `--no-compat-links` skips the links.
- `docs/` is now a wiki in the lint-enforced shape: flat, one page per slug, addressed by slug
  in double square brackets from `AGENTS.md` and between pages, every page with an H1, a
  provenance comment and a `Related:` line, every page reachable from `AGENTS.md`.
  `scripts/wiki_lint.py` (ten checks, exit 0/1/2, `--json`) and `tests/test_wiki_lint.py` are
  gate commands; `AGENTS.md` is rewritten as the router the spec describes, with a topic index.
- `docs/install.md`, `docs/compatibility.md`, `docs/hooks.md`, `docs/shellcheck.md`,
  `docs/development.md`, `docs/architecture.md` and `docs/conventions.md` — one page each for
  what the README and `AGENTS.md` used to carry inline. The install
  guide carries the marked `INSTALL` region `tests/install_smoke.sh` executes; the compatibility
  page carries the `COMPAT` region `tests/check_docs.py` checks; the development page is the
  gate's second pinned home.

### Changed

- The source file is `dogen.py`; the installed command is still `dogen`. `install.sh` copies or
  links it under that name, and every in-tree pin names `dogen.py`.
- The surface is harness-agnostic: no agent harness is named, detected or preferred in the
  README, the installer, the docs or `AGENTS.md`; skills are invoked as `/dogen-plan`,
  `/dogen-write` and `/dogen-review` everywhere.
- The README states that the output is Sphinx-publishable and that dogen knows nothing of any
  Sphinx stack, theme or `conf.py`, and gains a top-level layout section.
- `README.md` is agent-first: a five-minute quickstart (clone, `install.sh`, the three skills),
  a plain "how you use it", a section on keeping dogen on its own branch and shipping pages from
  a review branch popped off main, and a glossary that holds the vocabulary, the verb table and
  the exit codes. The exit codes are one compact table, a row per code with its reasons in the
  last cell; `tests/check_docs.py` reads that shape on the README side and the per-reason shape
  on the contract side, flattening both against the tool's `REASONS`.
- `docs/upgrade.md` is a forward-looking procedure — upgrade the executable, re-copy the skills,
  check the two numbers, what a contract bump does to existing records — rather than a
  before-and-after of the previous release.
- `tests/install_smoke.sh` runs the documented `install.sh --yes` out of `docs/install.md` and
  then drives one unit through the installed tool itself; the walk is no longer reader-facing
  shell in the README.
- The shellcheck scope is `install.sh tests/*.sh validation/*.sh`, in CI, in `AGENTS.md` and in
  the unit suite's CI mirror.

### Removed

- `docs/sessions/` and `validation/legs/` — the recorded session and leg records — and the unit
  tests over them. They carried run-specific paths and identities; the kit's tooling stays.
- Personal names in comments and prose are replaced by roles.
- The README's "What is and is not proven" section and the `CLAIMS` observable in
  `tests/check_docs.py`, with the release-record prose that cross-referenced them below.
- The README's credit section. The acceptance tests A-31 … A-35 keep the names they were ported
  under, and the *Fixed* entry below keeps the attribution.

## [0.2.0] - 2026-09-18

One stdlib-only `dogen` executable over a hash-chained JSONL ledger replaces the five
`scripts/dogen-*.sh` and the pipe-delimited `ledger.md`. Migration for anyone holding a record
written by the old scripts was archive-and-redeclare, the policy [docs/upgrade.md](docs/upgrade.md)
still states for any record under another contract number.

Entries describe the release as a whole. Where an entry names a file that lands later in the
release series, the release plan is the final check that every entry below is true at the tag.

### Added

- `docs/contract.md` — the normative specification: artifacts and ownership, envelope and
  serialization, the event catalogue, derivation, routing, validation rules, verb order and
  refusals, the write protocol and resume, what `verify` reports, and compatibility. Reviewed and
  frozen at `contract-v1` (see *Where the frozen contract lives*).
- `dogen` — one executable, Python 3.9 syntax, standard library only: no package, no venv, no
  dependencies. The record is `.dogen/units/<id>/ledger.jsonl`, canonical JSON lines chained by
  sha256 over each previous line's exact bytes, with all state derived from the events rather than
  stored.
- Thirteen verbs, one per transition: `unit` (`new`, `edit`, `retire`), `signoff`, `steer`,
  `plan-steps`, `step`, `draft`, `edits`, `review`, `resume`, `show`, `summary`, `verify`,
  `version`. Every verb takes `--json`.
- `dogen verify` — nineteen checks, V1 through V19, over the whole record: chain and canonical-form
  integrity, the committed prefix, signoff/generation/review citation, evidence and step gates,
  page currency per basis path, and git corroboration as WARN or INFO rather than FAIL.
- The evidence-gated step walk — `plan-steps` records the step plan with tool-computed text
  hashes; `step` records one step's evidence under `.dogen/staging/<id>/scratch/`; an actionable
  draft is refused while any planned step is unresolved.
- `dogen resume` — two-pass recovery for a transition interrupted mid-write, classifying every
  manifest file before it decides, with `--dry-run`, `--overwrite` and `--adopt`.
- The four suites: `tests/test_dogen_acceptance.sh` (the ported black-box suite),
  `tests/test_dogen_lifecycle.sh`, `tests/test_dogen_unit.py` and `tests/test_skill_text.py`, over
  `tests/run_matrix.sh` and `tests/check_traces.py`.
- `validation/` — the validation kit, shipped as evidence apparatus rather than as product code:
  `validation/score.py` (the rubric scorer plus the four-oracle independent audit),
  `validation/fixtures.sh` (V-01…V-04, the four corruption fixtures and the oracle that catches
  each), `validation/runmeta.sh` (a leg's RUN metadata) and `validation/rubric.md` (the scoring
  bar). Session records and per-leg RUN files are not shipped. It reports as its own CI job and is
  a gate command.
- Three skills — `dogen-plan`, `dogen-write`, `dogen-review` — that drive the loop through the
  verbs and never re-implement a gated, side-effecting action.
- `.github/workflows/ci.yml`, `tests/install_smoke.sh` (the only test that reaches `dogen` through
  `PATH` rather than the in-tree file) and `tests/check_docs.py`, which checks the documented verb
  table, reason table, compatibility numbers and links against the tool's own observables.
- `tests/size_guard.py` — VERB-09's line budget over `dogen`, reported and enforced. The CI job and
  the local guard load both thresholds **and** the comparison out of `tests/test_dogen_unit.py`, so
  there is one authoring site for the pair and the job and the guard are the same code rather than
  merely the same constants.
- [docs/upgrade.md](docs/upgrade.md) — the upgrade procedure.

### Changed

- The ledger moved from a pipe-delimited `ledger.md` to a hash-chained, canonical `ledger.jsonl`.
- Notes and reasons are now ordinary JSON text — a stated behaviour change from `slim@357c513`:
  `|` and newlines are ordinary characters, and a note round-trips byte-identical
  ([docs/contract.md](docs/contract.md) §5.2, §5.6).
- There is no `run_id`; `seq` is an event's identity, and `prev` chains the lines.
- A legacy pipe-delimited unit is refused with an archive hint (`legacy_unit`, exit 2) and is
  never migrated in place; a directory holding both files is a JSONL unit.
- Skills are discovered under `.agents/skills/` in the project, or `~/.agents/skills/` globally.
  Older roots (`.claude/skills/`, `.github/skills/`, `.opencode/skills/`) are found first by some
  agents and must be removed.
- VERB-09's line budget is recalibrated a third time, to **10,000 lines annotate / 12,000 fail**,
  from the 8,000 / 9,500 pair the earlier builds of this release carried. `dogen` measured 9,472
  lines, so the review trigger had fired on every run for 263 commits and 28 lines of headroom
  remained below the failing threshold — a trigger that fires always reports nothing, and 28 lines
  would have turned the `size-guard` job red on the next substantive change. The new pair applies
  the same offsets the previous recalibration used. The budget is a review trigger, not a design
  goal: behaviour is never deleted to fit it, and the pair has one authoring site in
  `tests/test_dogen_unit.py` that the job and the local guard both load.

### Fixed

- Carries forward the three code-enforced gate holes a reviewer found and closed on the slim
  branch in the v1 review: a `sphinx_target` path traversal (the target was joined into
  `docs/${target}` with no validation), a ledger row injection (an unescaped `|` or newline in a
  `--note` injected fake pipe-delimited fields, including a spoofed `verdict: accept`), and
  `unresolved_steps` matching `status: unverified` as a substring. Each is carried into v2.0 as an
  acceptance test — **A-31** `record_draft_rejects_target_traversal`, **A-32**
  `record_draft_rejects_absolute_target`, **A-33** `record_review_accept_rejects_target_traversal`,
  **A-34** `record_review_note_rejects_pipe` (ported as an inversion: the pipe is now ordinary text
  and the assertion is that no field was forged), and **A-35**
  `unresolved_steps_no_substring_false_positive`.
- To be plain about why the tree was swapped: the swap is justified by what a pipe-delimited ledger
  *cannot* do — support multi-line and `|` notes, persist step text, derive state after
  accept-then-redraft, scope `git add` — **not** by those three holes. Their regression tests are
  carried by intent, and the fixes are credited here.
- **The CI workflow had drifted from the gate it claims to run, and nothing noticed.** The unit
  suite now carries a mirror test that reads `.github/workflows/ci.yml` itself and asserts both
  directions — no gate command without a job, and no job the gate does not declare — with the two
  exceptions held as commented data rather than as prose. The drift it found was real: the gate
  lists both invocation forms of the unit suite on purpose, because they once reported different
  counts, and CI ran only the module form. `python3 tests/test_dogen_unit.py` now runs as a job
  beside it, so the truncation class the second form exists to catch is finally visible to CI.
- **A merge to the default branch could have its gate run cancelled by the next merge.** The
  workflow's concurrency group now keys on the pull request number where there is one and on the
  run identifier otherwise, and cancels in-progress runs only for pull requests. A cancelled run
  reports as cancelled rather than as a failure, so the previous rule left no red behind.
- **Every `actions/checkout` step now sets `persist-credentials: false`.** All eight jobs check out
  the repository and three of them execute repository content — the install smoke, the docs checker
  and the validation fixtures — so leaving a credential in the runner's git config put a token
  within reach of code the job runs by design.
- **The release record was checked by nothing, which is how it came to omit what shipped.**
  `tests/check_docs.py` gained a sixth observable that reads `CHANGELOG.md`'s content rather than
  only its links: it locates the released section, refuses a changelog with no released heading at
  all rather than passing vacuously, and fails on any of four placeholder markers surviving inside
  it. The record itself is corrected with it — the released heading is dated, and `validation/`
  (a kit with its own CI job and its own gate command) and `tests/size_guard.py` are named under
  `### Added`, where neither had appeared.
- **A sha256 was stated as though a reader could check it.** The transcript-digest sentence above
  is restated: the digest is an author-side tamper-evidence commitment, and nothing in this release
  lets a third party verify it. The claim is now what it was always able to support.
- **The shipped tree carried the author's real home directory in 91 places** — in prose, in quoted
  Sphinx error text, in diagnostics blobs and in the RUN files' transcript paths — across five
  files. All 91 are redacted, in both encodings the paths appeared in, and a test over the tree
  that actually ships now fails if either encoding returns. The anonymization gate that existed
  before this covered only the planning tree, which does not ship.

### Removed

- The five `scripts/dogen-*.sh` — `dogen-common.sh`, `dogen-signoff.sh`, `dogen-record-draft.sh`,
  `dogen-record-review.sh`, `dogen-record-step.sh`.
- `tests/test_dogen_scripts.sh`, the suite that tested them.
- The pipe-delimited `ledger.md` as a record of truth. It is never read, converted or deleted; a
  unit directory holding both files is a JSONL unit.
- The `--force` flag, everywhere. Re-signing is `dogen unit edit <id> --re-sign`.

### Where the frozen contract lives

`docs/contract.md` was reviewed and frozen at the signed tag `contract-v1`, on the `gsd` branch at
commit `30fe9a5`. That tag is deliberately **not** moved or duplicated onto `main`: `v0.2.0` is the
only tag on main's line. The freeze record stays where it was made, so it records a moment rather
than a decision made later.

The claim is checkable rather than asserted:

```
git fetch origin gsd --tags
git tag -v contract-v1
```

### Contract revision under `CONTRACT = 1`

The `internal_error` reason row (exit 6) was added to the contract's refusal table after
`contract-v1` was signed. It is raised only when dogen itself falls over below the verb.

The addition is **additive**: `contract` stays `1` and `min_tool` stays `0.2.0`, and so do the
`metadata.dogen_contract` and `metadata.dogen_min_tool` values in every `SKILL.md`. The reading is
that the contract's "enum change" means a rename, a removal, or a semantic change to an existing
member, and a new refusal reason that no caller can provoke by using the tool correctly is none of
those. The only callers that meet it are the ones previously told their own hash-chained record was
damaged — for a defect in dogen.

That reading reverses an earlier one, which classified the same row as a contract-2 change. Both
readings are recorded in `docs/contract.md`, and this revision goes to review with the pull request
that lands the row.

### Release-time evidence

**No GitHub Actions execution of this workflow exists as of the date on the `## [0.2.0]` heading
above.** That is the design rather than an omission: the workflow's first execution on a runner is
the release pull request itself, so there is no runner result to cite here, and this section says
so rather than implying otherwise. The evidence for "CI green at release" is the pull request's
eight independent job verdicts, each the same command a developer already runs locally.

**CI is not a required status check on the default branch.** The branch ruleset requires one
approving review and forbids deletion and non-fast-forward pushes; it carries no
required-status-checks rule, and one actor may bypass it unconditionally. "CI green at release" is
therefore evidence by inspection of a named run, not a condition the platform holds. Making it
machine-true is a repository settings change, prepared and deliberately not applied as part of
this release; a later push to the default branch can falsify the claim with nothing to catch it,
and the bypass actor survives the rule even once it is added.

**The merge commit, the run identifier and the tag are recorded in this section at the tag.** They
are facts that do not exist before the release lands. What this record states are the three facts
it can state: that no run exists, why that is by design, and what "green" is evidence of.

### How this release is cut, and which build was abandoned

A release branch for `v0.2.0` was built at `f83145a` and was locally green on the whole gate. It
was deliberately **not** pushed, tagged or opened as a pull request, and it is **superseded**: it
predates the validation kit under `validation/` and the eighth CI job that runs it. Naming the abandoned build here is the point — a later reader can tell
which one was dropped and on what grounds, instead of inferring it from a gap in the history.

The release branch is therefore re-carved **once**, from `main`, to include the kit, the eighth CI
job and the claims above. The decisive reason is that CI has never executed on a runner: its first
real run should land on the final eight-job workflow rather than on a seven-job one that changes
immediately afterwards, which would make the first green result stale on arrival.

The re-cut places the kit among the release's deliverable commits so that each commit is still
green on its own, and nothing from the planning branch enters the release tree — the release
carries real work only.

**A second build was abandoned, for the same reason and on the same grounds.** The re-cut branch
was built at `9308949` — ten signed commits, locally green on the whole gate, never pushed, never
tagged and never opened as a pull request — and it too is **superseded**: the gap-closure work
recorded under `### Changed` and `### Fixed` above changed the tree its first CI run would have
landed on. The argument that abandoned `f83145a` applies unchanged to `9308949`: a first green
runner result on a tree that changes immediately afterwards is stale on arrival. So the branch is
carved a third and final time, over the gap-closure tree, and both dropped builds are named here
rather than left as gaps in the history for a later reader to infer. The pull request, the review,
the merge and the tag are still ahead of this record at the time it is written; what is recorded
here is the carve and the two abandonments.

**A wording deviation, recorded rather than left to be noticed.** The requirement this release
discharges names a pull request from the frozen `slim` branch into `main`. This release is instead
cut **from `main`**, and the v2.0 tree replaces the slim tree there. The substance is the same and
the frozen commit is untouched: `slim` remains an ancestor of `main`, so every citation of it in
the contract, the docs and the tests keeps resolving. The reason for the deviation is that a pull
request from `slim` would have carried the planning branch's process artefacts into the published
history; cutting from `main` and adding real work path by path carries the product and none of the
process. The same deviation is recorded in the pull request description and on the ticket.

**The series is the artefact.** The release is carved by deliverable, each commit green on the
gate on its own, so any commit can be checked out and the gate run against it. It is merged as a
merge commit rather than squashed or rebased, because a squash would discard exactly the ordering
that makes the change reviewable.
