# dogen skill family contract

The **normative family contract** for the portable Agent Skills vendored in this
directory. Portable `SKILL.md` files are dogen's primary human-facing surface — the
loop a Technical Author (TA) actually drives, backed by 4 deterministic bash scripts
that enforce the load-bearing guarantees. Every `dogen-*` skill follows this contract.

The skills are conversational LLM prompts (no flags) that invoke the deterministic
scripts (`scripts/dogen-signoff.sh` / `dogen-record-draft.sh` /
`dogen-record-review.sh` / `dogen-record-step.sh`) via `Bash`, and write/edit files
directly for non-load-bearing operations (writing `unit.md`, appending steering
notes). The skills carry **intent and judgment**; the scripts hold the **provable
HITL gate**, the **WR-03 write ordering**, the **evidence micro-gate**, and the
**commit seam** — a skill never re-implements a gated, side-effecting action, it
delegates it.

This README is the **maintainer source of truth**. The agentskills.io loading model
auto-loads each `SKILL.md` but never this README, so anything a skill must execute
at runtime is physically embedded in each `SKILL.md`.

## Pipeline

```
dogen-plan -> dogen-write   -> dogen-review
           \-> dogen-record -> dogen-review
```

- **dogen-plan** — grounds itself in the repo's prior art (`.dogen/context/`
  artifacts and existing docs conventions), runs the Socratic intake, writes
  `unit.md`, and ends with the gate act (`dogen-signoff.sh`). Also serves
  advise-only triage asks ("does this need docs?") with a grounded Triage
  Recommendation, declaring nothing until the TA says go. Routes on Diátaxis
  direction: reference/explanation → dogen-write; tutorial/how-to → dogen-record.

- **dogen-write** — drafts a review-ready reference or explanation page (MyST or
  rST — the unit's target extension decides). The host agent authors the page
  from the declared sources, stages it under `.dogen/staging/`, and records it
  via `dogen-record-draft.sh` (which enforces the HITL gate inline, writes the
  ledger row before the page, and checks for identical redrafts).

- **dogen-record** — walks the TA through an evidence-gated step plan and drafts
  a tutorial or how-to from what actually ran. Each step's verbatim proof (bytes
  + exit code + SHA-256) is recorded via `dogen-record-step.sh`; the final page
  is recorded via `dogen-record-draft.sh` (same as dogen-write).

- **dogen-review** — surfaces the drafted unit for human review through two modes
  (record / review with 5-dimension findings), then records the verdict via
  `dogen-record-review.sh`. Accept seals page SHA-256 hashes; fix/redraft append
  the note to the steering stream. Never edits the draft.

## The deterministic scripts

| Script | Enforces | Called by |
|---|---|---|
| `dogen-signoff.sh` | HITL gate: SHA-256 of `unit.md` + commit; lazy-creates ledger | dogen-plan |
| `dogen-record-draft.sh` | Inline gate + WR-03: ledger before page + identical-redraft | dogen-write, dogen-record |
| `dogen-record-review.sh` | Verdict recording: accept seals hashes / fix\|redraft appends steering | dogen-review |
| `dogen-record-step.sh` | Evidence micro-gate: validates verdict + SHA-256 + staleness; fail stays unverified | dogen-record |

Every script emits one local git commit with `Dogen-Unit:` / `Dogen-Phase:`
trailers, staging only `.dogen/` and `docs/` (never the whole repo). Scripts never
push, open PRs, build, or publish.

## The ledger

The on-disk audit trail at `.dogen/units/<id>/ledger.md` (plain markdown,
pipe-delimited rows). Sections: `## signoff`, `## steering`, `## generations`,
`## reviews`, `## steps`. The first line (`# dogen ledger — unit: <id>`) is the
compaction-recovery anchor. State (`pending`/`drafted`/`reviewed`) and sealed-ness
are derived by grepping the ledger — nothing is stored as a flag.

## Installation

Copy the skills into your harness's discovery root:

```bash
# Claude Code:
cp -r skills/dogen-* .claude/skills/

# GitHub Copilot CLI:
cp -r skills/dogen-* .github/skills/

# opencode:
cp -r skills/dogen-* .opencode/skills/
```

Copy the scripts onto your PATH (or reference them by relative path from the repo root):

```bash
cp scripts/dogen-*.sh /usr/local/bin/   # or: export PATH="$PWD/scripts:$PATH"
```

## Vocabulary

- **sealed** — a unit whose latest review is an **accept**. Derived from the
  ledger's `## reviews` section.
- **ledger** — the plain-markdown audit trail at `.dogen/units/<id>/ledger.md`.
  Records signoff, steering, generations, reviews, and steps.
- **gate** — the signoff act recorded by `dogen-signoff.sh`. `dogen-record-draft.sh`
  checks it inline before recording any draft.

## Licensing

The skills under `skills/` are licensed under **Apache-2.0** (see `LICENSE`).
The scripts under `scripts/` are licensed under **LGPL-3.0-only** (see the root
`LICENSE`).
