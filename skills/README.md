# dogen skill family contract

The **normative family contract** for the portable Agent Skills vendored in this
directory. Portable `SKILL.md` files are dogen's primary human-facing surface — the
loop a Technical Author (TA) actually drives, backed by 4 deterministic bash scripts
that enforce the load-bearing guarantees. Every `dogen-*` skill follows this contract.

The skills are conversational LLM prompts (no flags) that invoke the deterministic
scripts (`dogen-signoff.sh` / `dogen-record-draft.sh` /
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
dogen-fetch -> dogen-plan -> dogen-write -> dogen-review
```

- **dogen-fetch** — prepares reusable style, terminology, structure, and
  provenance artefacts from explicitly declared sources. Use it when the target
  repository does not already have reliable `.dogen/context/` files.

- **dogen-plan** — grounds itself in the repo's prior art (`.dogen/context/`
  artifacts and existing docs conventions), runs the Socratic intake, writes
  `unit.md`, and ends with the gate act (`dogen-signoff.sh`). Also serves
  advise-only triage asks ("does this need docs?") with a grounded Triage
  Recommendation, declaring nothing until the TA says go. Routes on Diátaxis
  direction: all four directions → dogen-write.

- **dogen-write** — the sole drafting skill, covering all four directions
  (reference / explanation / tutorial / how-to) in two modes. Reference and
  explanation author the page straight from the declared sources; tutorial and
  how-to walk an evidence-gated step plan and draft from what actually ran, each
  step's verbatim proof (bytes + exit code + SHA-256) recorded via
  `dogen-record-step.sh`. Either way the host agent stages the page under
  `.dogen/staging/` and records it via `dogen-record-draft.sh` (which enforces
  the HITL gate inline, writes the ledger row before the page, checks for
  identical redrafts, and exits 4 on unresolved actionable steps).

- **dogen-review** — surfaces the drafted unit for human review through two modes
  (record / review with 5-dimension findings), then records the verdict via
  `dogen-record-review.sh`. Accept seals page SHA-256 hashes; fix/redraft append
  the note to the steering stream. Never edits the draft.

### dogen-onboard (repo-level, occasional)

- **dogen-onboard** — outside the per-unit pipeline. Walks the repo's documentation
  surfaces and produces the three `.dogen/context/` artifacts (`doc-style.md`,
  `glossary.md`, `structure.md`) that later ground `dogen-plan`. The
  skill authors the three files under `.dogen/staging/context/`; the recorder
  (`dogen-record-context.sh`) refuses any unrecognized artifact, promotes the staged
  files into `.dogen/context/`, freezes a manifest (one SHA-256 per file), and
  commits with `Dogen-Phase: onboard`. It is a context recorder, not one of the
  four gates. Replaces the earlier standalone Python docs-scraper.

## The deterministic scripts

| Script | Enforces | Called by |
|---|---|---|
| `dogen-signoff.sh` | HITL gate: SHA-256 of `unit.md` + commit; lazy-creates ledger | dogen-plan |
| `dogen-record-draft.sh` | Inline gate + WR-03: ledger before page + identical-redraft; exits 4 on unresolved actionable steps | dogen-write |
| `dogen-record-review.sh` | Verdict recording: accept seals hashes / fix\|redraft appends steering | dogen-review |
| `dogen-record-step.sh` | Evidence micro-gate: validates verdict + SHA-256 + staleness; fail stays unverified | dogen-write |

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

Point a `DOGEN` variable at your dogen checkout, then install the scripts (system-wide)
and the skills (project-scoped or global):

```bash
DOGEN=/path/to/dogen-mvp-1

# Scripts — onto your PATH (once, system-wide, so they work from any repo):
sudo cp "$DOGEN"/scripts/dogen-*.sh /usr/local/bin/
#   or, without sudo:
mkdir -p ~/.local/bin && cp "$DOGEN"/scripts/dogen-*.sh ~/.local/bin/

# Skills — into the agent-compatible discovery root, project-scoped or global:
# Project-scoped (recommended) — copy into each docs repo:
cd /path/to/your-docs-repo
cp -r "$DOGEN"/skills/dogen-* .agents/skills/
# Global — copy once, so every repo discovers them:
mkdir -p ~/.agents/skills && cp -r "$DOGEN"/skills/dogen-* ~/.agents/skills/
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
