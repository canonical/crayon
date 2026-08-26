# Middle-Path Implementation Plan

> **Goal:** Reimagine dogen as a superpowers-style skill set with a thin deterministic
> script layer — removing the Python CLI/core while preserving load-bearing guarantees
> (HITL gate, provenance ordering, evidence verification, accept sealing) via 6 small
> bash scripts that skills invoke via `Bash`.

## 1. Architecture overview

```
skills/                          ← the human-facing surface (SKILL.md)
├── dogen-plan/SKILL.md
├── dogen-write/SKILL.md
└── dogen-review/SKILL.md

scripts/                         ← the deterministic enforcement layer (4 scripts + common)
├── dogen-common.sh              ← shared helpers (SHA-256, ledger ops, path validation, commit)
├── dogen-signoff.sh             ← HITL gate: hash unit.md, lazy-create ledger, commit "signoff"
├── dogen-record-draft.sh        ← inline gate check + WR-03: ledger before page + identical-redraft, commit "draft"
├── dogen-record-review.sh       ← record verdict (accept seals hashes / fix|redraft appends steering), commit "review"
└── dogen-record-step.sh         ← evidence micro-gate (fail stays unverified), commit "step"

tests/
└── test_dogen_scripts.sh        ← bash test suite for all 6 scripts

docs/
├── middle-path-plan.md          ← this document
└── before-after.md              ← concise mapping (orig → new)
```

**What's removed:** `src/dogen/` (Python core + CLI + adapters), `pyproject.toml`'s
`[project.scripts]`, the Copilot SDK dependency, Pydantic, Typer, logfire, opentelemetry,
import-linter, `seam_check.py` (vacuous without `core/`).

**What's kept:** the 3 `SKILL.md` files (rewritten), `skill_lint.py` (relaxed — all skills
may `Write`), the `.dogen/` on-disk layout, the Diátaxis routing, the commit-trailer grammar.

**What's new:** the ledger (`ledger.md` replaces `provenance.yaml`), the 6 scripts, the
Drill eval harness outline (§8).

## 2. Feature mapping — current → new

| Feature | Current (CLI + Python core) | New (scripts + skills) | Status |
|---|---|---|---|
| HITL gate | `SignoffRequiredError` in `orchestrator.py` | `dogen-signoff.sh` computes SHA-256; `dogen-record-draft.sh` refuses inline | **Preserved** (structural) |
| Provenance-first write ordering (WR-03) | `draft` writes `provenance.yaml` before page | `dogen-record-draft.sh` writes ledger row before copying page | **Preserved** (structural) |
| Identical-redraft suppression (D-02) | Byte-hash compare in `orchestrator.py` | `dogen-record-draft.sh` compares SHA-256, no-ops on match | **Preserved** (structural) |
| Evidence micro-gate (v1.2) | `record_step` refuses done-without-proof | `dogen-record-step.sh` validates verdict enum, requires SHA-256 + exit_code + step_text_sha256; fail stays unverified | **Preserved** (structural) |
| Evidence-incomplete refusal (actionable units) | prose-enforced "resolve all steps before drafting" | `dogen-record-draft.sh` exits 4 on unresolved steps for an actionable unit | **Preserved** (structural — now code-enforced) |
| Review recording | `review` seals hashes / appends steering in `provenance.yaml` | `dogen-record-review.sh` handles accept (seals) / fix / redraft (appends steering) | **Preserved** (structural) |
| Commit trailers | `_commit_transition` with `Dogen-*` trailers | Each script emits its own `Dogen-*` trailers | **Preserved** (structural) |
| Schema validation | Pydantic v2 models with validators | None — ledger is plain markdown | **Lost** |
| v0→v1→v2 migration | Lazy `Provenance._migrate` on load | None — new format starts at v1 | **Lost** (no migration needed) |
| Derived state on read | `derive_progress()`, `is_sealed()` | Skills derive by grepping the ledger | **Changed** (prose-enforced) |
| Provider seam | `DraftingProvider` port + `seam_check.py` + import-linter | Not applicable — driver mode removed | **Removed** |
| Driver mode (Copilot SDK) | `CopilotDraftingProvider` headless session | Removed — host agent is always the drafter | **Removed** |
| Passenger mode | `HostHarnessDraftingProvider` | The only mode — host agent drafts, script records | **Simplified** |
| Passenger honesty (T-03-03) | Code prevents fabricating driver provenance | Automatically preserved — no driver mode to impersonate | **Preserved** (by removal) |
| Routing (`_suggest_next`) | `next_id` token from `orchestrator.py` | Skills derive from ledger state in prose | **Changed** (prose-enforced) |
| Multi-owner lease (D-04) | `resolve_owners` scans all units | Skills grep all ledgers; best-effort | **Changed** (prose-enforced) |
| `--json` contract | Every verb emits JSON with `reason` code | Not applicable — no CLI | **Removed** |
| `dogen status` | Repo-wide board from all provenance files | Skill reads ledgers; best-effort | **Changed** (prose-enforced) |
| `dogen unit ls/show/rm/mv` | CLI verbs | Skills manage files directly | **Changed** (prose-enforced) |
| `dogen steer` | CLI verb appends to steering stream | Skill appends to ledger via `Edit` | **Changed** (prose-enforced) |
| `dogen provider/model/commits` | CLI config verbs | Not applicable — no driver, no config | **Removed** |
| `dogen context add/ls` | CLI verb for `.dogen/context/` | Skill manages files directly | **Changed** (prose-enforced) |
| `dogen skills install/status/update` | CLI verb | `cp -r` or a thin install script | **Simplified** |
| Observability (OTel/logfire) | `core/observability.py` + `obs/logfire_backend.py` | The ledger IS the observability record | **Removed** (replaced by ledger) |
| `skill_lint.py` write-isolation | Only dogen-write/dogen-record may `Write` | Relaxed — all 3 skills may `Write` (to the ledger) | **Changed** |
| Testability (57 test files) | pytest asserting gate/ordering/routing/seam | ~1 bash test file for scripts + Drill evals | **Reduced** (scripts tested; skills eval'd) |

## 3. On-disk artifacts

### 3.1 The ledger (`ledger.md` replaces `provenance.yaml`)

Location: `.dogen/units/<unit-id>/ledger.md`

```markdown
# dogen ledger — unit: pipeline-definition

## signoff
2026-08-17T12:00:00+00:00 | author: Rusty Kratky | plan_hash: abc123... | commit: def456...

## steering
2026-08-17T12:05:00+00:00 | author: Rusty Kratky | origin: manual | Cover the YAML merge policy.

## generations
2026-08-17T12:10:00+00:00 | model: "" | provider: host-harness | mode: passenger | file: docs/reference/pipeline-definition.rst | sha256: ghi789... | run_id: jkl012... | steering_count: 1

## reviews
2026-08-17T12:30:00+00:00 | reviewer: Rusty Kratky | verdict: accept | sealed: docs/reference/pipeline-definition.rst:mno345... | note: Looks good.

## steps
step-1 | text_hash: pqr678... | status: resolved | exit_code: 0 | output_sha256: stu901... | verdict: pass | mode: agent
step-2 | text_hash: vwx234... | status: unverified
```

Design properties:
- **Human-readable** — a TA can read and debug it in any editor.
- **Grep-friendly** — `grep "^## signoff"`, `grep "plan_hash:"`, `grep "verdict: accept"`.
- **Compaction-survivable** — first line `# dogen ledger — unit: <id>` is the recovery anchor.
- **Append-only** — rows are never edited (except step status updates by `dogen-record-step.sh`).
- **No schema validation** — the scripts write well-formed rows; skills are trusted to append
  well-formed steering notes.

### 3.2 `unit.md` (unchanged)

The editable human plan with YAML frontmatter (`unit_id`, `intent`, `audience`, `title`,
`sources`, `sphinx_target`, `extra_targets`, `steering_notes`). Scripts parse the
`sphinx_target` field to know where to write the draft.

### 3.3 `.dogen/` layout

```
.dogen/
├── context/                    # B1/B2 landing zone (unchanged)
├── staging/<unit-id>/          # passenger scratch (unchanged, gitignored)
└── units/<unit-id>/
    ├── unit.md                 # editable human plan (unchanged)
    └── ledger.md               # the audit trail (replaces provenance.yaml)
```

## 4. Scripts — deterministic enforcement layer

All scripts live in `scripts/`, are bash, use `set -euo pipefail`, and follow these conventions:
- **Exit codes:** 0 = success, 1 = gate refusal, 2 = bad input, 3 = no-op (e.g. identical redraft)
- **Output:** human-readable progress on stdout; errors on stderr
- **Commits:** each state-changing script emits one git commit with `Dogen-*` trailers
- **No push:** scripts never push, open PRs, build, or publish

### 4.1 `dogen-signoff.sh <unit-id> [--force]`

The HITL gate act. Lazy-creates the ledger if it doesn't exist (folds the old init-unit step).

- **Validates:** `unit.md` exists at `.dogen/units/<id>/unit.md`
- **Lazy-creates:** `ledger.md` with `# dogen ledger — unit: <id>` header if missing
- **Computes:** `plan_hash = sha256(unit.md)`, `head_commit = git rev-parse HEAD`
- **Gate:** refuses if signoff row already exists with same `plan_hash` (unless `--force`)
- **Writes:** signoff row to `## signoff` section of `ledger.md`
- **Commits:** `Dogen-Unit: <id>`, `Dogen-Phase: signoff`
- **Exit 1** if already signed off at this hash; **exit 2** if `unit.md` missing

### 4.2 `dogen-record-draft.sh <unit-id> <draft-file> [--model <model>]`

Records a drafted page. Inlines the gate check (folds the old verify-gate step). WR-03: ledger before page.

- **Validates:** `unit_id` against path traversal
- **Inline gate:** checks signoff exists + plan hash matches (exit 1 if no signoff or stale plan)
- **Reads:** `sphinx_target` from `unit.md` frontmatter → determines `docs/<target>` path
- **Identical-redraft check:** SHA-256 of `<draft-file>` vs last generation's `sha256` — if
  match, exit 3 (no-op, no commit)
- **Ordering:** (1) writes generation row to `## generations` in `ledger.md`; (2) copies
  `<draft-file>` to `docs/<target>`; (3) commits (staging only `.dogen/` + `docs/`)
- **Commits:** `Dogen-Unit: <id>`, `Dogen-Phase: draft`, `Dogen-Draft: <sha256[:12]>`
- **Exit 1** if gate fails; **exit 2** if bad input; **exit 3** if identical redraft

### 4.3 `dogen-record-review.sh <unit-id> --verdict accept|fix|redraft [--note <text>] [--note-file <path>]`

Records a structured review verdict. Accept seals page hashes; fix/redraft appends the note to the steering stream.

- **Validates:** `unit_id` against path traversal; `--verdict` must be `accept`, `fix`, or `redraft`
- **Gate:** at least one generation must exist in the ledger (exit 1)
- **On accept:** computes SHA-256 of the drafted page, writes review row with `verdict: accept` and `sealed: <path>:<hash>`
- **On fix/redraft:** appends steering row (origin: review) + review row; `--note` is required (exit 2 if missing)
- **Commits:** `Dogen-Unit: <id>`, `Dogen-Phase: review`, `Dogen-Verdict: <verdict>`
- **Exit 1** if no generation; **exit 2** if bad input

### 4.4 `dogen-record-step.sh <unit-id> <step-id> --evidence-file <path>`

Evidence micro-gate for tutorial/how-to steps.

- **Validates:** `unit_id` against path traversal; `verdict` must be `pass`/`fail`/`skipped`/`deviated`
- **Required fields:** `output_sha256` + `exit_code` for pass/fail; `output_sha256` + `reason` for skipped/deviated; `step_text_sha256` always required
- **Staleness:** reads `step_text_sha256` from evidence, compares to current step text hash in ledger
- **Updates:** step row in `## steps` section — sets `status: resolved`, writes evidence fields
- **Commits:** `Dogen-Unit: <id>`, `Dogen-Phase: step`, `Dogen-Step: <step-id>`
- **Exit 1** if evidence incomplete; **exit 2** if bad input; **exit 3** if stale evidence

## 5. Skills — human-facing surface

### 5.1 Changes common to all 3 skills

- **`allowed-tools`:** all three gain `Write` and `Edit` (to write `unit.md` and append to
  `ledger.md`). `skill_lint.py` is relaxed to allow this.
- **Delegation:** skills no longer call `dogen unit new` / `dogen signoff` / etc. They call
  the 6 scripts via `Bash`, and write/edit files directly for non-load-bearing operations.
- **Bootstrap:** a `references/bootstrap.md` in each skill reminds the agent to check the
  ledger before acting (compaction recovery).

### 5.2 `dogen-plan/SKILL.md`

**Today:** Socratic intake; delegates to `dogen unit new` / `edit` / `signoff`.
**New:**
- Socratic intake (unchanged prose)
- Writes `unit.md` directly via `Write`
- Calls `scripts/dogen-signoff.sh <id>` via `Bash` → HITL gate act (lazy-creates ledger)
- Appends steering notes directly to `ledger.md` via `Edit` (under `## steering`)
- **`<HARD-GATE>` block:** "Do NOT invoke `dogen-write` until
  `dogen-signoff.sh` has been called and exited 0."
- **Terminal state:** routes on Diátaxis direction — all four directions → `dogen-write`
  (reference/explanation author straight; tutorial/how-to take the evidence-walk branch).
  Prose: "The ONLY skill you invoke after dogen-plan is dogen-write, per the declared intent."

### 5.3 `dogen-write/SKILL.md`

**Today:** Delegates to `dogen draft --draft-file/--report` (passenger) or `dogen draft` (driver).
**New:**
- **Driver mode removed.** The host agent is always the drafter.
- **Branches on the declared `intent`** — the sole drafting skill, covering all four directions:
  - **reference / explanation** — agent reads the declared sources, navigates the repo, authors
    the page straight from the sources.
  - **tutorial / how-to** — evidence-walk branch: writes the step plan to `ledger.md` under
    `## steps` via `Edit` (each step: `step-N | text_hash: <sha256> | status: unverified`); for
    each step runs it, captures evidence (exit code, output SHA-256, excerpt) to a temp file, and
    calls `scripts/dogen-record-step.sh <id> <step-id> --evidence-file <evidence>` via `Bash` →
    verifies evidence, updates step status, commits.
- Stages the draft under `.dogen/staging/<id>/handoff/<target>`
- Writes a context report (what it read) to `.dogen/staging/<id>/report.md`
- Calls `scripts/dogen-record-draft.sh <id> <staged-draft> --model <model> --report <report>`
  via `Bash` → WR-03 ordering, identical-redraft check, exit 4 on unresolved actionable steps, commit
- **Iron Law:** "Do NOT write the page directly to `docs/`. Stage it, then call
  `dogen-record-draft.sh`." / "Do NOT mark a step resolved without calling `dogen-record-step.sh`."
- **Terminal state:** "The ONLY skill you invoke after dogen-write is dogen-review."

### 5.4 `dogen-review/SKILL.md`

**Today:** Delegates to `dogen review --verdict --note`.
**New:**
- Two modes (unchanged): `record` (compact summary + verdict) and `review` (5-dimension findings)
- For all verdicts: calls `scripts/dogen-record-review.sh <id> --verdict <accept|fix|redraft> --note <text>` via `Bash` → accept seals page hashes; fix/redraft appends note to steering stream; all in one atomic commit
- **Iron Law:** "Do NOT record a verdict without calling `dogen-record-review.sh`."

## 6. Tests

### 6.1 Script tests (`tests/test_dogen_scripts.sh`)

A bash test script that sets up a temp git repo and exercises each script:

```
test_init_unit_happy_path       — init creates ledger, commits
test_init_unit_missing_unit_md  — exit 2
test_signoff_happy_path         — signoff writes row, commits
test_signoff_double_signoff     — exit 1 without --force
test_signoff_force              — --force overwrites
test_verify_gate_pass           — exit 0 after signoff
test_verify_gate_no_signoff     — exit 1
test_verify_gate_stale_plan     — exit 2 after unit.md edited post-signoff
test_record_draft_happy_path    — ledger before page, commits
test_record_draft_gate_refusal  — exit 1 without signoff
test_record_draft_identical     — exit 3 on byte-identical redraft
test_seal_accept_happy_path     — seals hashes, commits
test_seal_accept_no_generation  — exit 1
test_record_step_happy_path     — verifies evidence, updates step
test_record_step_stale_evidence — exit 3
test_record_step_incomplete     — exit 1
test_commit_trailers            — grep Dogen-Unit/Dogen-Phase in git log
```

### 6.2 What's no longer tested

The 57 pytest files asserting orchestrator behavior, CLI contracts, the seam, routing tokens,
ownership leases, etc. are removed. The scripts cover the load-bearing guarantees; everything
else is measured by the Drill eval harness (§8).

## 7. `skill_lint.py` changes

- `WRITERS` set expanded from `{"dogen-write", "dogen-record"}` to include all three skills:
  `{"dogen-plan", "dogen-write", "dogen-review"}`
- The write-isolation gate is relaxed: all skills may carry `Write`/`Edit`
- Frontmatter validation (`name` matches directory, `description` present) stays
- The lint remains a pre-commit + CI gate

## 8. Drill eval harness — outline (implementation deferred)

### Purpose

Measure skill compliance probabilistically — the superpowers model. The scripts give structural
guarantees for the load-bearing pieces; the eval harness measures whether the skills actually
invoke them at the right times, in the right order, with the right prose.

### Architecture (outlined)

```
dogen-evals/                     ← separate repo (like superpowers-evals)
├── scenarios/                   ← one YAML per test scenario
│   ├── declare-reference.yaml
│   ├── declare-tutorial.yaml
│   ├── draft-without-signoff.yaml   ← negative: should refuse
│   ├── redraft-identical.yaml       ← negative: should no-op
│   └── review-accept.yaml
├── runners/
│   ├── run-claude.sh            ← tmux-driven Claude Code session
│   ├── run-copilot.sh           ← Copilot CLI session
│   └── run-opencode.sh          ← opencode session
├── verifier/
│   └── verify.py                ← LLM-judged compliance check
├── results/                     ← scored transcripts + verdicts
└── Makefile                     ← make test, make test-fast, make test-full
```

### Scenario format

```yaml
# scenarios/declare-reference.yaml
name: "Declare a reference unit, sign off, draft, review"
harness: [claude, copilot, opencode]
setup:
  - init temp git repo
  - create source files
prompt: |
  I need reference docs for the pipeline-definition module.
  The sources are src/dogen/core/models.py and src/dogen/cli/main.py.
  Target: reference/definition-files/pipeline-definition.rst
checks:
  - skill_invoked: dogen-plan
  - script_called: dogen-signoff.sh
  - file_exists: .dogen/units/pipeline-definition/ledger.md
  - ledger_has_section: signoff
  - skill_invoked: dogen-write
  - script_called: dogen-record-draft.sh
  - file_exists: docs/reference/definition-files/pipeline-definition.rst
  - ledger_has_section: generations
  - skill_invoked: dogen-review
  - script_called: dogen-record-review.sh
  - ledger_has_section: reviews
  - ledger_row_contains: reviews, verdict: accept
negative_checks:
  - no_draft_before_signoff: true
  - no_direct_write_to_docs: true
```

### Phases

1. **Phase 1 (deferred):** Stand up the `dogen-evals` repo. Port Drill's tmux harness.
   Write 5 core scenarios (declare+draft+review for reference and tutorial; two negative
   scenarios). Run manually.
2. **Phase 2 (deferred):** Add the LLM verifier. Score compliance per scenario per harness.
   Nightly runs.
3. **Phase 3 (deferred):** Add regression scenarios for every bug found in the wild.

### What the evals measure (that the scripts can't)

- Does the skill actually invoke `dogen-signoff.sh` before `dogen-record-draft.sh`?
- Does the skill refuse to draft when the gate fails?
- Does the skill write to `docs/` directly (bypassing the script)?
- Does the skill correctly route on Diátaxis direction?
- Does the skill append steering notes on `fix`/`redraft` verdicts?
- Does the skill recover correctly after compaction (re-read the ledger)?

## 9. README changes

The README is rewritten to reflect:
- **No Python install** — just copy skills + scripts into the repo
- **No CLI** — the skills are the entire interface
- **Install:** `cp -r skills/dogen-* .agents/skills/ && cp scripts/dogen-*.sh /usr/local/bin/`
  (or a thin `install.sh`)
- **Smoke check:** the same declare→signoff→draft→review loop, but driven from the harness
- **Develop:** the test suite is `bash tests/test_dogen_scripts.sh`, not `uv run pytest`

## 10. Migration path (for existing dogen repos)

Existing repos with `.dogen/units/<id>/provenance.yaml` would need a one-time migration:
- Run `scripts/migrate-provenance-to-ledger.sh <unit-id>` (not yet written)
- Converts `provenance.yaml` → `ledger.md` (best-effort field mapping)
- Commits with `Dogen-Phase: migrate`
- The old `provenance.yaml` is left in place for audit (not deleted)

This migration script is **out of scope** for this plan — it's a follow-up if/when existing
dogen repos need to move to the new format.
