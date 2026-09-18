# dogen

**dogen** is a documentation-drafting tool for Technical Authors: it drafts review-ready,
**Sphinx-publishable** documentation (MyST Markdown or reStructuredText, Diátaxis-structured)
from human-pointed sources, human-in-the-loop, and deliberately stops at the boundary of a
single traceable local commit. Its guarantees live in one stdlib-only executable — the `dogen`
file at the repo root, one verb per transition over a hash-chained JSONL ledger, with its
behaviour fixed by [`docs/contract.md`](docs/contract.md) — driven by three portable Agent
Skills.

## Scope border (the hard line)

dogen **drafts and stops at a single, traceable local commit.** It stays deliberately "dumb"
outside drafting:

- It does **not** push, open or review pull requests, build, or auto-publish.
- A human owns intent and review of every draft; human-in-the-loop steering is **mandatory
  and recorded** — dogen refuses to produce a substantial draft without it.
- The reviewer/merger owns the shipped output — there is no "AI-generated" disclaimer,
  because humans stand behind what ships.

---

## Install and first run

The three install steps and the walk that follows them are one copy-pasteable block. Paste it
into a scratch repo and it runs end to end; CI runs **the same bytes** on every push, extracted
from between the two markers below by [`tests/install_smoke.sh`](tests/install_smoke.sh), so
this section cannot rot silently.

Run it in a **scratch directory**: step 3 runs `git init` and sets a repo-local git identity,
which you do not want pointed at a repository you care about.

```bash
mkdir -p /tmp/dogen-try && cd /tmp/dogen-try    # outside the markers: your scratch repo
```

<!-- QUICKSTART:BEGIN -->

Two shell defaults control every path below. Edit them in place, or export them
before you start — nothing else in this walk needs adjusting.

```bash
DOGEN_SRC="${DOGEN_SRC:-$HOME/src/dogen}"   # your checkout of dogen
REPO="${REPO:-$PWD}"                        # the docs repo you are documenting
```

#### 1 — Put `dogen` on your PATH

`dogen` is a single stdlib-only Python executable. No venv, no package, no `sudo`:
copy it into your own `~/.local/bin` and put that on `PATH`.

```bash
mkdir -p "$HOME/.local/bin"
cp "$DOGEN_SRC/dogen" "$HOME/.local/bin/dogen"
chmod +x "$HOME/.local/bin/dogen"
export PATH="$HOME/.local/bin:$PATH"
dogen version --json
```

#### 2 — Install the skills into the docs repo

The three skills (`dogen-plan`, `dogen-write`, `dogen-review`) are the surface your
agent drives. Copy them into the repo's `.agents/skills/` discovery root, so they
travel with the repo:

```bash
mkdir -p "$REPO/.agents/skills" && cp -r "$DOGEN_SRC"/skills/dogen-* "$REPO/.agents/skills"
```

#### 3 — Prepare the repo

`dogen` records every transition as a local git commit, so it needs a git repo and a
git identity. It also stages drafts under `.dogen/staging/`, which is working space
and belongs in `.gitignore` — without that line `verify` ends on a warning (V17).

```bash
cd "$REPO"
git init -q -b main .
git config user.name "Anne Example"
git config user.email "anne@example.com"
grep -qxF '.dogen/staging/' .gitignore 2>/dev/null \
  || printf '.dogen/staging/\n' >> .gitignore
printf '# Widget API\n\nCreate and delete widgets.\n' > source.md
mkdir -p docs
printf '# Docs\n' > docs/index.md
git add -A
git commit -q -m "seed the docs repo"
```

#### 4 — Walk one unit from declaration to a written page

Declare the unit and its sources, sign the plan off (the human-in-the-loop gate),
steer it, then record a draft. `steer` is load-bearing, not decorative: without a
steering record `draft` refuses with `unsteered`.

```bash
printf '# Plan\n\nOutline the widget API reference.\n' \
  | dogen unit new widget-api \
      --intent reference \
      --audience "developers integrating the widget API" \
      --title "Widget API" \
      --target reference/widget-api.md \
      --source source.md \
      --body-file -

dogen signoff widget-api

dogen steer widget-api --note "Lead with the create call."

mkdir -p .dogen/staging/widget-api/draft
printf '# Widget API\n\n## create\n\nCreates a widget.\n' \
  > .dogen/staging/widget-api/draft/widget-api.md
dogen draft widget-api .dogen/staging/widget-api/draft/widget-api.md
```

#### 5 — Check the record and see where you are

```bash
dogen verify widget-api
dogen show widget-api
```

`verify` reports `verdict: ok · … · 0 warn · 0 fail` over the whole record; `show`
reports the derived state and the page it wrote — `reference/widget-api.md`, which
lands on disk at `docs/reference/widget-api.md`. Both are read-only.

<!-- QUICKSTART:END -->
### Installing the skills globally instead

The walk installs the skills project-scoped, so they travel with the docs repo — the
recommended scope, repeated once per repo and re-run after upgrading dogen. The alternative is
a single global copy that every repo discovers (each line creates the directory it copies into,
so it works in a fresh checkout):

```bash
mkdir -p "$HOME/.agents/skills" && cp -r "$DOGEN_SRC"/skills/dogen-* "$HOME/.agents/skills"
```

Modern agents read the agent-compatible `.agents/skills/` (project) or `~/.agents/skills/`
(global) discovery root, rather than the harness-specific `.claude/`, `.github/` or
`.opencode/` roots.

---

## How you actually use it

The walk above is the mechanical path — it proves the install. The real entry point is the
skills, driven from your agent harness, which is why it sits outside the markers: a shell
script cannot drive an agent. You talk to the agent; the agent calls the verbs.

1. **`dogen-plan`** — declare a unit and its sources, shape the outline, record your intent and
   audience, and sign the plan off. The signoff is the human-in-the-loop gate: it freezes the
   plan hash, and nothing substantial may be recorded against the unit until it exists.
2. **`dogen-write`** — the sole drafting skill, and the only one allowed to write. It branches
   on the declared `intent`: **reference** and **explanation** are drafted from the signed-off
   plan and its sources; **tutorial** and **how-to** are drafted *by doing*, through an
   evidence-gated step walk that captures verbatim output bytes, exit codes and SHA-256 digests,
   so the page is authored from what actually ran.
3. **`dogen-review`** — review the draft alongside its provenance and record a verdict
   (**accept** / **fix** / **redraft**). Accept seals the page digests and closes pending
   requests by recorded disposition; fix and redraft append to the steering stream.

Every skill opens by reading the tool's own view of the unit and routes on the `next` token it
reports, so you can drop the conversation and resume in a fresh one without losing your place.

The gate is enforced in code, not by convention: `draft` refuses — with no side effects — until
a signoff is on record and the plan hash is current, and refuses again if nothing has been
steered since the last generation. When you are done, the draft sits in local commits for you
to review and merge. dogen never pushes.

### A few words that mean something specific

- **unit** — one documentation unit: a declared intent, audience, title, source list and one or
  more target pages, recorded in `.dogen/units/<id>/unit.md`.
- **ledger** — the record of truth at `.dogen/units/<id>/ledger.jsonl`: hash-chained JSONL, one
  canonical line per event, append-only. State is *derived* by reading it; nothing is stored.
- **basis** — the set of pages, with their recorded digests, that the record currently stands
  behind. Bytes on disk that differ from the basis are *drift*, and drift is reported, never
  silently overwritten.
- **sealed** — a unit whose latest review is an **accept**.

### Add context files (recommended)

Context files teach dogen your house style, vocabulary, and where facts live. They land in
`.dogen/context/`:

```bash
mkdir -p .dogen/context
cp path/to/your-style-guide.md .dogen/context/doc-style.md
cp path/to/glossary.md .dogen/context/glossary.md
```

Well-known names the skills look for: `doc-style.md`, `glossary.md`, `structure.md`,
`code-to-docs-map.md`, `doc-gaps.md`.

---

## Verbs

One row per subcommand `dogen --help` registers. The normative definition of each verb's
preconditions, no-ops and content gates is [`docs/contract.md`](docs/contract.md) §5.7 and §6 —
this table is a reader-facing projection of it, never a second specification.

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

---

## Exit codes and refusals

A non-zero exit prints **exactly one JSON line** with the five keys `error`, `unit`, `detail`,
`hint` and `next` — on stderr, or on stdout under `--json`. `error` is the machine-readable
field: branch on it, not on the exit code, which several reasons share.

<!-- REASONS:BEGIN -->

| Exit | Band |
|---|---|
| `0` | success |
| `1` | gate — a precondition of the transition is not met |
| `2` | bad input — unknown unit or step, missing file, path traversal, unknown flag |
| `3` | no-op — the request is already on the record; nothing to do |
| `4` | evidence — missing, unresolved, stale or mismatched step evidence |
| `5` | busy — another dogen run or another git process holds a lock |
| `6` | ledger and recovery — the record needs attention before the tool may write |

Every reason the tool can emit, with its exit code:

| Reason | Exit |
|---|---|
| `no_signoff` | 1 |
| `plan_stale` | 1 |
| `page_drift` | 1 |
| `target_exists` | 1 |
| `target_missing` | 1 |
| `generation_stale` | 1 |
| `unapplied_steering` | 1 |
| `unsteered` | 1 |
| `no_generation` | 1 |
| `target_claimed` | 1 |
| `retired` | 1 |
| `bad_target` | 2 |
| `bad_write_path` | 2 |
| `bad_draft_path` | 2 |
| `bad_resolution` | 2 |
| `unit_invalid` | 2 |
| `unit_exists` | 2 |
| `unit_not_found` | 2 |
| `step_unknown` | 2 |
| `not_actionable` | 2 |
| `note_required` | 2 |
| `git_identity_missing` | 2 |
| `not_a_repo` | 2 |
| `legacy_unit` | 2 |
| `identical_draft` | 3 |
| `already_signed` | 3 |
| `already_accepted` | 3 |
| `already_recorded` | 3 |
| `already_retired` | 3 |
| `no_edits` | 3 |
| `noop_unchanged` | 3 |
| `nothing_to_resume` | 3 |
| `steps_unresolved` | 4 |
| `steps_missing` | 4 |
| `evidence_stale` | 4 |
| `evidence_incomplete` | 4 |
| `evidence_mismatch` | 4 |
| `busy` | 5 |
| `git_busy` | 5 |
| `ledger_corrupt` | 6 |
| `ledger_version_unsupported` | 6 |
| `unit_id_mismatch` | 6 |
| `uncommitted_tail` | 6 |
| `ledger_diverged` | 6 |
| `resume_ambiguous` | 6 |
| `recovery_unsupported` | 6 |
| `adopt_unsupported` | 6 |
| `internal_error` | 6 |

<!-- REASONS:END -->

The authoritative list is the tool's own `REASONS` table and
[`docs/contract.md`](docs/contract.md) §5.7; the region above is checked against both.

---

## Compatibility

<!-- COMPAT:BEGIN -->

| Number | Value |
|---|---|
| `contract` | `1` |
| `min_tool` | `0.2.0` |

`dogen version --json` reports both. A skill stops on exactly two conditions: a `contract`
number that is not the one it was written against, or a tool older than `min_tool`. Nothing
else about a version is checked, and the two numbers are compared as literal strings — never
parsed or rounded as versions.

<!-- COMPAT:END -->

A ledger whose header event carries a different `contract` is never half-read: every verb
refuses it, read-only ones included. Legacy units are archived, never migrated in place — see
[`docs/upgrade.md`](docs/upgrade.md).

---

## Formatting hooks on target pages

If a `pre-commit` hook reformats the pages dogen writes, the supported behaviour is
**adoption**, and the routes say so:

- **The hook rewrites the page and the commit succeeds.** The transition stands — it is
  committed. The verb exits 0 with the warning `hook changed <path> after recording`, re-derives
  state, and routes you to `dogen edits`. Recording the hook's bytes as your edits makes them
  the basis. That is the steady state: adopt once, and the hook's output is what the record
  stands behind.
- **The hook rewrites the page and rejects the commit.** The transition is incomplete and the
  tool says so (`uncommitted_tail`), routing you at `dogen resume`. Where the rewritten bytes
  are not the ones dogen intended, `resume` stops and offers the two choices explicitly —
  `--overwrite` to re-place the intended bytes, or `--adopt --note` to keep the hook's. A second
  failed commit on the same batch is refused rather than retried: a hint that reproduces its own
  refusal is not an escape.

What is **not** supported is a hook that *deletes* the placed file. There are no current bytes
to adopt, so `--adopt` refuses. A formatter is not a reviewer; adoption always records a note
saying a hook changed the bytes and the author retained them.

---

## Shellcheck policy

The bash suites and the install smoke are kept clean at `shellcheck -S warning`. CI runs the
shellcheck **preinstalled on the runner image, version 0.9.0**, rather than downloading a
newer one — a pinned download or a third-party action would add supply-chain surface to a gate
whose whole job is to be boring. A developer machine is likely to have a newer shellcheck, so a
finding can in principle appear on one side and not the other.

The rule when that happens: **reproduce the CI-only finding against the pinned 0.9.0 before
changing any code.** A fix written against a newer analyzer's model of the same script is a
guess, and a guess committed to silence a gate is how a gate stops meaning anything.

---

## Upgrading from the previous release

If you hold records written by the previous bash-era release, read
[`docs/upgrade.md`](docs/upgrade.md) before you run this one: it states every behaviour change
as a before → after pair — notes are ordinary JSON text now, `seq` is the event identity, and
legacy units are archived rather than migrated. [`CHANGELOG.md`](CHANGELOG.md) is the release
record for `v0.2.0`.

---

## What is and is not proven

<!-- CLAIMS:BEGIN -->

Two capabilities this tool offers were carried here as **not yet validated by a real run**. Both
have since been driven by real authoring sessions, and each is replaced below by the evidence that
discharged it rather than by an assurance that it works:

- **Multi-file support is proved.** Validation unit `schema-section-consistency` recorded a
  `generation` carrying two `files[]` entries — `reference/definition-files/sdk-definition.rst`
  and `reference/definition-files/sdkcraft-definition.rst` — committed in the target repository at
  `15bcba0073beadc372a9827405c1aca46bcf0025`. The audit corroborates it from an angle that shares
  no code with the tool: `oracle-3` reports two sealed pages hashing to the digest the basis
  recorded, and `oracle-4` reports two recorded target paths in the basis vocabulary. The record
  is `validation/legs/RUN-workshop-definition.codex-cli.json`.
- **The evidence-gated step walk has been driven in a real session.** Validation unit
  `validate-workshop-definition` planned four steps, recorded a resolution with tool-captured
  evidence for each, and drafted and accepted a how-to; the draft is committed in the target
  repository at `fd153bf` and the record is
  `validation/legs/RUN-validate-workshop-definition.json`. **That session did not prove the loop
  produces a how-to grounded in observed command behaviour, and this release does not claim it.**
  Three of the four steps resolved `skipped` — `workshop` and `sdkcraft` are snaps and
  snap-confine could not start in that environment — so the accepted page carries successful
  command evidence for one step of four, and three quarters of the documented procedure rests on
  code reading rather than on observed behaviour.

Neither statement above is a claim that the loop produces a usable draft. Of the three recorded
validation walks, one met the pre-registered bar for a usable draft on every graded dimension and
two did not; the scores are in `validation/legs/workshop-definition.md` and
`validation/legs/validate-workshop-definition.md`, as measured, and no walk was re-run to improve
one.

A third boundary carries over from the recorded authoring sessions: **they ran against fixture
hooks, not a repository's own configured hooks.** Both hook shapes above were installed from the
test fixtures because the repository's own `pre-commit` could not run in that environment, so
the hook routes are proven against the shapes, not against a real project's hook configuration.

**Supported configurations are unproven, and none is listed.** No install session was run for
this release: both legs fell back, on 2026-09-16, to the wording declared before either of them
could have run — *no non-implementer session was run; supported configurations unproven*, and
*AC1 unproven*. A configuration that no recorded session exercised is not named here as
supported, so this section lists none rather than guessing at a list.

Nothing is substituted for the sessions that did not happen. An implementer, an agent driving a
session on someone's instruction, and a simulated reader are each a stand-in, and a stand-in
would make this section evidence about something other than what it claims. The two recorded
authoring sessions under `docs/sessions/` were themselves agent-driven, so the measurements that
matter most to a first-time reader — avoidable questions, and help requests — have never had a
human-hands reading in this milestone. An agent-reported zero is a different claim from a
human-observed zero, and this release has only the former.

The evidence behind the two discharged statements is in the tree and can be re-run rather than
taken on trust. `validation/score.py` re-scores a unit against an oracle that shares no code with
`dogen`; `validation/fixtures.sh` re-runs the four corruption fixtures; `validation/rubric.md` and
the per-leg files under `validation/legs/` are the standard, committed before either session ran;
and each `validation/legs/RUN-<leg>.json` carries the skills and tool digests, the baseline commit,
the six session metrics, the Sphinx before/after evidence and the transcript's sha256. The session
transcripts themselves do **not** ship — only their shas, inside those RUN files. That digest is a
commitment, not something a reader can verify: it lets the author prove later that a transcript
produced on request is the one the record was written against. Nothing in this release lets a third
party check it, and this section does not claim otherwise.

<!-- CLAIMS:END -->

Supported configurations are named from recorded install evidence only, and the statement above
is the whole of that evidence for this release. `CHANGELOG.md` records what is missing and why,
rather than substituting a stand-in for it.

---

## Credit

The v1.x bash layer's three audit holes were found and closed by **the reviewer** on
2026-08-31:

- **`sphinx_target` path traversal**, in both the draft-recording and the accept paths — a
  target that escaped the docs root could have bytes written to it.
- **Ledger note delimiter injection** — the ledger was pipe-delimited, so a `|` inside a note
  was a field separator, and a crafted note could write a verdict the reviewer never gave.
- **An `unresolved steps` substring false positive** — the unresolved-step check grepped the
  ledger text, so prose that merely contained the words of a status was read as that status.

His regression tests are carried into v2.0 by intent as acceptance tests **A-31…A-35**, each
named in `tests/test_dogen_acceptance.sh` after the function it came from, so a reviewer looking
for them finds them by name. Two are ported as inversions, because v2.0 removed the mechanism
the original defended: `|` and newlines are ordinary characters in a JSON note, and step status
is derived from a `verdict` field rather than from text.

To be clear about why the rewrite happened: it is justified by what a pipe-delimited ledger
cannot do — carry multi-line and `|`-bearing notes, persist step text, derive state after an
accept-then-redraft, scope `git add` — not by those three holes, which were fixed where they
were found.

---

## Develop dogen itself

The gate has one home: [`AGENTS.md`](AGENTS.md) states every command a commit must be green on,
in full. Run those. This file deliberately does not restate them, so the two cannot disagree.

## Licensing

The tool is licensed under **LGPL-3.0-only** (see [`LICENSE`](LICENSE)). The portable skills
under [`skills/`](skills/) are licensed separately under **Apache-2.0** (see
[`skills/LICENSE`](skills/LICENSE)).
