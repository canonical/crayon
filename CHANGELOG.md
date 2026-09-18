# Changelog

All notable changes to dogen are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/): `Added`, `Changed`, `Fixed`, `Removed`,
in that order under every release. Within a heading, entries run in the order the deliverables land
in the release series — contract and tool core, the four suites, skills over verbs, the retired v1
bash layer, CI and the install smoke, the docs, the session records — so two entries of equal
significance still have one order a reader can predict.

## [Unreleased]

Nothing unreleased. This section is stated rather than omitted: an empty heading reads as an
oversight, a stated one reads as a fact.

## [0.2.0] - 2026-09-18

One stdlib-only `dogen` executable over a hash-chained JSONL ledger replaces the five
`scripts/dogen-*.sh` and the pipe-delimited `ledger.md`. Migration for anyone holding a record
written by the old scripts is [docs/upgrade.md](docs/upgrade.md).

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
  each), `validation/runmeta.sh` (a leg's RUN metadata), `validation/rubric.md` (the scoring bar)
  and `validation/legs/` (the pre-registered per-leg checklists and their RUN files). It reports as
  its own CI job and is a gate command.
- Three skills — `dogen-plan`, `dogen-write`, `dogen-review` — that drive the loop through the
  verbs and never re-implement a gated, side-effecting action.
- `.github/workflows/ci.yml`, `tests/install_smoke.sh` (the only test that reaches `dogen` through
  `PATH` rather than the in-tree file) and `tests/check_docs.py`, which checks the documented verb
  table, reason table, compatibility numbers and links against the tool's own observables.
- `tests/size_guard.py` — VERB-09's line budget over `dogen`, reported and enforced. The CI job and
  the local guard load both thresholds **and** the comparison out of `tests/test_dogen_unit.py`, so
  there is one authoring site for the pair and the job and the guard are the same code rather than
  merely the same constants.
- [docs/upgrade.md](docs/upgrade.md) — the migration page for a `slim@357c513` record, and
  `docs/sessions/` — the install-session records and the template they instantiate.

### Changed

- The ledger moved from a pipe-delimited `ledger.md` to a hash-chained, canonical `ledger.jsonl`.
- Notes and reasons are now ordinary JSON text — a stated behaviour change from `slim@357c513`.
  Detail: [docs/upgrade.md](docs/upgrade.md) §1.
- There is no `run_id`; `seq` is an event's identity. Detail: [docs/upgrade.md](docs/upgrade.md) §2.
- A legacy pipe-delimited unit is refused with an archive hint and is never migrated in place.
  Detail: [docs/upgrade.md](docs/upgrade.md) §3.
- Skills are discovered under `.agents/skills/` in the project, or `~/.agents/skills/` globally.
  Detail: [docs/upgrade.md](docs/upgrade.md) §6.
- VERB-09's line budget is recalibrated a third time, to **10,000 lines annotate / 12,000 fail**,
  from the 8,000 / 9,500 pair the earlier builds of this release carried. `dogen` measured 9,472
  lines, so the review trigger had fired on every run for 263 commits and 28 lines of headroom
  remained below the failing threshold — a trigger that fires always reports nothing, and 28 lines
  would have turned the `size-guard` job red on the next substantive change. The new pair applies
  the same offsets the previous recalibration used. The budget is a review trigger, not a design
  goal: behaviour is never deleted to fit it, and the pair has one authoring site in
  `tests/test_dogen_unit.py` that the job and the local guard both load.
- Both install-session records now carry a **`Relationship to the team`** field between `Author`
  and `Agent runtime`, reading `stand-in` and stating plainly that every metric in the record is
  agent-reported. The field is not decoration: it moves the agent-reported-versus-human-observed
  boundary from an inference a reader had to draw off the `Author:` line into a recorded fact. The
  record shape itself is now mirrored from `docs/sessions/TEMPLATE.md` and asserted against it, so
  the list of declared fields cannot outlive what it mirrors.

### Fixed

- Carries forward the three code-enforced gate holes the reviewer found and closed on the slim
  branch in his 2026-08-31 review: a `sphinx_target` path traversal (the target was joined into
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
  accept-then-redraft, scope `git add` — **not** by those three holes. His regression tests are
  carried by intent, and the fixes are credited here and in the README.
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

### Install evidence and claims boundary

**No install session was run for this release.** Both legs REL-03 asks for fell back, on
2026-09-16, to the wording declared before either of them could have run:

- **no non-implementer session was run; supported configurations unproven**
- **AC1 unproven**

Those two sentences were fixed in advance, while stating them was still costless, precisely so
this paragraph could not be drafted afterwards to suit whatever happened. They are reproduced
verbatim, here and in `README.md`'s claims boundary; nothing softens them and nothing is
substituted for them. No implementer ran either session instead, and no agent driven on someone's
instruction is recorded as a reader — the earlier precedent, an agent CLI session recorded in
place of two named readers, is deliberately not repeated.

#### What the install evidence is, and what it is not

The install evidence behind this release is the two **authoring** sessions under `docs/sessions/`
— `2026-09-14-early.md` and `2026-09-15-full.md` — and nothing else. Read plainly, that is:

- Both were driven by an agent CLI on the author's instruction, not by a reader meeting the
  document for the first time. Every metric in them is agent-reported.
- The two measurements REL-03 cares about most — avoidable questions, and help requests — have
  therefore **never had a human-hands reading anywhere in this milestone**. An agent-reported zero
  is a different claim from a human-observed zero, and this release has only the former.
- Where those records write `not measured`, no number is reported for that metric here. An
  unmeasured metric stays unmeasured in the release notes.
- **Both legs ran against fixture hooks, not a repository's own configured hooks.** The hook
  shapes were installed from the test fixtures because the repository's own `pre-commit` could not
  run in that environment, so the hook routes are proven against the shapes and not against a real
  project's hook configuration. Every hook row in those records carries that provenance
  explicitly, which is what makes the distinction checkable rather than asserted.

**Supported configurations are therefore unproven, and none is named** — a configuration no
recorded session exercised is not listed as supported. That is stated rather than omitted: an
absent section reads as an oversight, a stated one reads as a fact.

#### The honest-claims boundary

Carried here in full rather than cross-referenced. Two of the statements this section held were
discharged by real authoring sessions, and each is replaced by the evidence rather than removed:

- **Multi-file support is proved.** Validation unit `schema-section-consistency` recorded a
  `generation` carrying two `files[]` entries — `reference/definition-files/sdk-definition.rst`
  and `reference/definition-files/sdkcraft-definition.rst` — committed in the target repository at
  `15bcba0073beadc372a9827405c1aca46bcf0025`. An oracle sharing no code with the tool agrees from
  the other side: two sealed pages hashing to the digest the basis recorded, and two recorded
  target paths in the basis vocabulary. The record is
  `validation/legs/RUN-workshop-definition.codex-cli.json`.
- **The evidence-gated step walk has been driven in a real session.** Validation unit
  `validate-workshop-definition` planned four steps, recorded a resolution with tool-captured
  evidence for each, and drafted and accepted a how-to; the draft is committed in the target
  repository at `fd153bf` and the record is
  `validation/legs/RUN-validate-workshop-definition.json`. **That session did not prove the loop
  produces a how-to grounded in observed command behaviour, and this release does not claim it.**
  Three of the four steps resolved `skipped` — `workshop` and `sdkcraft` are snaps and
  snap-confine could not start in that environment — so the accepted page carries successful
  command evidence for one step of four.

Neither statement is a claim that the loop produces a usable draft. Of the three recorded
validation walks, one met the pre-registered bar on every graded dimension and two did not. The
scores stand as measured in `validation/legs/workshop-definition.md` and
`validation/legs/validate-workshop-definition.md`; no walk was re-run to improve one, and no
pre-registered expectation was edited after the session it graded.

The three statements the boundary still carries are unchanged: the fixture-hooks reading above,
the unnamed supported configurations above, and the grounding the actionable walk did not
establish. `tests/check_docs.py`'s `REQUIRED_CLAIMS` is keyed on all three, so dropping one from
`README.md` fails the `docs-check` job rather than passing quietly.

#### The validation evidence, and what a reader can re-run

The claims above rest on a kit that ships with the release, so a reader checks them rather than
takes them:

- `validation/fixtures.sh` re-runs the four corruption fixtures — a bypassed signoff gate, a
  tampered ledger line, an unsteered redraft and an unevidenced step — and each must still be
  caught.
- `validation/score.py audit` re-scores a unit against a four-oracle implementation that shares no
  code with `dogen`, so agreement between them is evidence and disagreement is reported as
  `DISAGREE` rather than resolved in the tool's favour.
- `validation/rubric.md` and the per-leg files under `validation/legs/` are the standard, and both
  were committed before either session ran. A score below a leg's own baseline row is recorded as
  measured; the leg is not re-run to improve it.
- Each `validation/legs/RUN-<leg>.json` carries the skills tree digest, the `dogen` digest, the
  baseline commit, the six session metrics, the Sphinx before/after evidence with an attribution
  for every new item, and the transcript's sha256.

**The session transcripts do not ship — only their shas, inside those RUN files.** That digest is a
commitment rather than something a reader can verify: it lets the author prove later that a
transcript produced on request is the one the record was written against. Nothing in this release
lets a third party check it, and this section does not claim otherwise.

The kit reports as its own CI job. A kit failure is never reported as a tool-suite failure, and a
tool-suite failure is never hidden behind a green kit.

#### Release-time evidence

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

#### How this release is cut, and which build was abandoned

A release branch for `v0.2.0` was built at `f83145a` and was locally green on the whole gate. It
was deliberately **not** pushed, tagged or opened as a pull request, and it is **superseded**: it
predates the validation kit under `validation/`, the eighth CI job that runs it, and the claims
boundary as it now stands. Naming the abandoned build here is the point — a later reader can tell
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
