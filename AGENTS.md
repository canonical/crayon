# AGENTS.md — operating contract for coding agents

Harness-neutral operating contract for any AI coding agent working in this repository
(read by Copilot, Codex, Cursor, and others; Claude Code reads it too). Read it before you
touch anything.

**Non-negotiables**

- **The deterministic scripts are the gate.** dogen's guarantees live in four bash scripts,
  not in skill prose and not in the model's discretion. Never weaken a script's check in
  exchange for a "nicer" skill prompt. The four are:
  - `dogen-signoff.sh` — the **HITL gate** (freezes `sha256(unit.md)` + the repo HEAD).
  - `dogen-record-draft.sh` — the **write gate** (refuses without a valid signoff; writes the
    ledger before the page — WR-03; no-ops on identical redraft; refuses actionable units with
    unresolved steps).
  - `dogen-record-review.sh` — the **verdict gate** (accept seals page hashes; fix/redraft
    appends the note to the steering stream).
  - `dogen-record-step.sh` — the **evidence micro-gate** (proves each tutorial/how-to step with
    bytes + exit code + SHA-256; a `fail` stays unverified).
- **No substantial draft without recorded human signoff.** dogen refuses to record a draft until
  `dogen-signoff.sh` has run and the plan hash still matches. The gate is code-enforced; never
  move it into the model's discretion.
- **dogen drafts and stops.** Each transition is one local git commit (with `Dogen-*` trailers);
  the scripts never push, open or review PRs, build, or publish. The reviewer/merger owns the
  shipped output.
- **The ledger is the provenance.** The on-disk audit trail is `.dogen/units/<id>/ledger.md`
  (plain markdown). Never invent a second record-of-truth; state is *derived* by reading it.
- **Skills are the surface; the scripts are the tool layer.** Technical Authors drive the
  `dogen-plan` / `dogen-write` / `dogen-review` / `dogen-record` skills; those skills invoke the
  deterministic scripts via `Bash`. Skills may `Write` only their staging files — never the
  canonical `docs/` page, never the ledger's gated sections directly.
- **`main` stays green.** `bash tests/test_dogen_scripts.sh` and `python3 scripts/skill_lint.py`
  must both pass before a commit lands.

The rest of this file is the project brief and architecture.

---

## Project

**dogen — skills-first documentation-drafting framework**

dogen drafts review-ready, **Sphinx-publishable** documentation (MyST Markdown or
reStructuredText, Diátaxis-structured) from human-pointed sources — human-in-the-loop — and
deliberately stops at the boundary of a single traceable local commit. It never pushes, reviews
PRs, builds, or publishes.

This iteration is a **pure-skills + bash rebuild**: portable Agent Skills (`SKILL.md`) are the
surface a Technical Author drives, backed by a thin layer of deterministic bash scripts that
enforce the load-bearing guarantees. There is no Python core, no CLI, no provider SDK — just
skills + scripts. (The earlier Python/Copilot-SDK prototype is this repo's history at tag
`archive/mvp-1-prototype`; the pure-skills rebuild supersedes it.)

**Core Value:** a Technical Author points dogen at sources for one documentation unit, steers it
on intent and audience, and gets a **review-ready, Sphinx-publishable draft** — produced through a
*provable* human-in-the-loop loop, with steering and provenance recorded on disk. If everything
else fails, this loop must work: declare → steer → draft → review, no substantial draft without
recorded human signoff.

### Constraints

- **No Python core.** dogen is bash scripts + `SKILL.md` files. `scripts/skill_lint.py` is a
  standalone stdlib-only lint utility (kept for the frontmatter gate); it is not a "core."
- **Surface**: portable Agent Skills (`SKILL.md`) to the **agentskills.io** spec, split into
  `dogen-plan` / `dogen-write` / `dogen-review` / `dogen-record`; validated on Claude Code and
  Copilot CLI.
- **Licensing**: scripts LGPL-3.0-only (single root `LICENSE`); skills Apache-2.0 (`skills/LICENSE`).
- **Agnosticism**: platform-agnostic — any harness that reads `SKILL.md` and exposes `Bash` +
  `Write` works; prove it on one stack (GitHub + RTD + Sphinx) this cycle.
- **Output**: Sphinx-publishable MyST Markdown (or rST where siblings are rST), Diátaxis-structured.
- **HITL / provenance**: no substantial draft without recorded signoff; provenance is internal
  observability, not a published "AI-generated" disclaimer.
- **UX**: "if it's easier to circumvent than to use, it will be circumvented."

## Architecture

```
skills/                         ← the human-facing surface (SKILL.md + references/)
├── dogen-plan/                 ← declare + HITL signoff (Socratic intake, routes on Diátaxis)
├── dogen-write/                ← draft reference/explanation from sources
├── dogen-review/               ← review + record the verdict (accept/fix/redraft)
└── dogen-record/               ← draft tutorial/how-to from an evidence-gated step walk

scripts/                        ← the deterministic enforcement layer
├── dogen-common.sh             ← shared helpers (SHA-256, ledger ops, path validation, commit)
├── dogen-signoff.sh            ← HITL gate: hash unit.md, lazy-create ledger, commit
├── dogen-record-draft.sh       ← write gate: inline signoff check, WR-03 ordering, identical-redraft
├── dogen-record-review.sh      ← verdict gate: accept seals hashes / fix|redraft appends steering
├── dogen-record-step.sh        ← evidence micro-gate: proves a step; fail stays unverified
└── skill_lint.py               ← SKILL.md frontmatter gate (standalone, stdlib-only)

tests/test_dogen_scripts.sh     ← the test suite (bash; no pytest)
```

### The scripts — exit-code contract

Every state-changing script emits one local git commit with `Dogen-Unit:` / `Dogen-Phase:`
trailers (plus `Dogen-Draft:` / `Dogen-Verdict:` / `Dogen-Step:` where relevant), staging only
`.dogen/` and `docs/`. Exit codes:

| Code | Meaning |
|------|---------|
| `0`  | success |
| `1`  | gate refusal — no signoff, stale plan, or evidence incomplete |
| `2`  | bad input — unknown unit/step, missing file, path traversal, unknown flag |
| `3`  | no-op — identical redraft, or stale step evidence |

`git log --grep 'Dogen-Unit: <id>'` replays a unit's whole path.

### The ledger

`.dogen/units/<id>/ledger.md` — plain markdown, pipe-delimited rows, sections `## signoff`,
`## steering`, `## generations`, `## reviews`, `## steps`. The first line
(`# dogen ledger — unit: <id>`) is the compaction-recovery anchor. `unit.md` (YAML frontmatter +
body) holds the plan: `unit_id`, `intent`, `audience`, `title`, `sources`, `sphinx_target`.

---

## Develop dogen itself

```bash
bash tests/test_dogen_scripts.sh     # 58 assertions across the script suite
python3 scripts/skill_lint.py        # 4 skills, frontmatter invariants
shellcheck scripts/dogen-*.sh        # if shellcheck is installed
```

## Conventions

- **Markup**: new drafted pages default to MyST Markdown (`colon_fence`); use rST when a page's
  siblings are already rST — the target extension *is* the format (`.md` → MyST, `.rst` → rST).
- **Diátaxis**: one direction per page (tutorial / how-to / reference / explanation); the direction
  is a declared field (`intent`) that routes the draft-stage skill.
- **Ledger**: append-only; rows are never edited except step-status updates by
  `dogen-record-step.sh`. Never hand-edit a gated section.
- **Commit seam**: the scripts own their commits (never run a competing `git add -A` / commit in a
  skill for a gated transition).