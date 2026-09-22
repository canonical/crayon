# dogen

**dogen** is a skills-first, agentic **documentation-drafting** framework for Technical
Authors. It drafts review-ready, **Sphinx-publishable** documentation (MyST Markdown or
reStructuredText, Diátaxis-structured) from human-pointed sources — human-in-the-loop — and
deliberately stops at the boundary of a single traceable local commit.

This iteration is a **pure-skills architecture**: portable Agent Skills (`SKILL.md`) are the
surface a Technical Author drives, backed by a thin layer of deterministic bash scripts that
enforce the load-bearing guarantees (HITL gate, provenance ordering, evidence verification,
accept sealing). No Python, no CLI, no venv — just skills + scripts.

- **Skills-first surface** — the portable `dogen-fetch` / `dogen-plan` / `dogen-write` /
  `dogen-review`
  skill family is the primary, harness-agnostic human interface.
- **Deterministic gates** — 4 bash scripts enforce the HITL gate, write ordering,
  identical-redraft suppression, evidence verification, and structured review
  recording (accept/fix/redraft). The model cannot bypass them.
- **Type-aware drafting**, steered by human intent, audience, and product expertise.
- **Sphinx-publishable output** — the target docs-as-code stack is GitHub + Read the Docs +
  Sphinx, structured along Diátaxis.
- **Zero Python install** — drop `scripts/` + `skills/` into any repo; works in any harness
  that reads `SKILL.md` and exposes `Bash` + `Write`.

## Project views

- [Project timeline](./project-timeline.html) — the Jira-backed history, current Pulse #19 work,
  backlog, dependencies, and September 14 decisions.
- [Planned v0.2 architecture](./dogen-architecture.html) — an interactive map of the proposed
  stdlib-only Python CLI, skills, optional onboarding and mapping flows, artifacts, boundaries,
  and the Jira work attached to each element. This is a target design; the current merged
  implementation remains the Bash-based slim baseline described below.

## Scope border (the hard line)

dogen **drafts and stops at a single, traceable local commit.** It stays deliberately "dumb"
outside drafting:

- It does **not** push, open or review pull requests, build, or auto-publish.
- A human owns intent and review of every draft; human-in-the-loop steering is **mandatory
  and recorded** — dogen refuses to produce a substantial draft without it.
- The reviewer/merger owns the shipped output — there is no "AI-generated" disclaimer,
  because humans stand behind what ships.

---

## Quickstart: use dogen in a docs repo

### 1 — Install the scripts and skills

dogen's scripts and skills live in your **dogen checkout**; you install them once and then use
them from any project repo. Point a `DOGEN` variable at your checkout so the commands below
work regardless of path:

```bash
DOGEN=/path/to/dogen-mvp-1       # your checkout of dogen
```

**Scripts — put them on your PATH (once, system-wide, so they work from any repo):**

```bash
# System-wide (requires sudo):
sudo cp "$DOGEN"/scripts/dogen-*.sh /usr/local/bin/

# …or to your user bin (no sudo; ensure ~/.local/bin is on PATH):
mkdir -p ~/.local/bin && cp "$DOGEN"/scripts/dogen-*.sh ~/.local/bin/
```

**Skills — install them at one of two scopes:**

```bash
# Project-scoped (recommended) — copy into each docs repo, so the skills travel with it:
cd /path/to/your-docs-repo
mkdir -p ~/.agents/skills && cp -r "$DOGEN"/skills/dogen-* .agents/skills/

# Global — copy once, so every repo discovers them:
mkdir -p ~/.agents/skills && cp -r "$DOGEN"/skills/dogen-* ~/.agents/skills/
```

Modern agents read the agent-compatible `.agents/skills/` (project) or `~/.agents/skills/`
(global) discovery root, rather than the harness-specific `.claude/`, `.github/`, or `.opencode/`
roots. Repeat the project-scoped copy in each docs repo (once per repo; re-run after upgrading dogen).

The scripts are the deterministic enforcement layer; the skills are the interface. Your agent
harness sees the `SKILL.md` files in the docs repo and invokes the scripts (which must be on
`PATH`) via `Bash`.

### 2 — Add context files (recommended)

Context files teach dogen your house style, vocabulary, and where facts live. They land in
`.dogen/context/`. By default, the skills look for: `doc-style.md`, `glossary.md`, `structure.md`,
`code-to-docs-map.md`, `doc-gaps.md`.

The `dogen-onboard` skill produces three common context files, i.e., `doc-style.md`, `glossary.md`,
and `structure.md` and adds them to the folder. You can also create the context files externally
and add them to the folder:

```bash
mkdir -p .dogen/context
cp path/to/your-style-guide.md .dogen/context/doc-style.md
cp path/to/glossary.md .dogen/context/glossary.md
```

For a deterministic `code-to-docs-map.md` and a `doc-gaps.md` based on the same, use the
[Code to docs mapper](https://code.launchpad.net/code-to-docs-mapper). This requires the code and
docs exist in separate collections in a vector database. These can be created using
[Wide scope RAG](https://code.launchpad.net/wide-scope-rag). Alternatively, the `dogen-plan` skill
can perform a live crawl but with less repeatable results.

### 3 — Draft a documentation unit

Drive the skills in order from your agent. They call the deterministic scripts and enforce
the human-in-the-loop gate at each step.

1. **`dogen-fetch` (optional)** — prepare project-specific style, terminology, structure, and
  provenance artefacts in `.dogen/context/` when the repository lacks reliable context.
2. **`dogen-plan`** — declare a unit and its sources, shape the outline, record your intent
   and audience, and **sign the plan off** (calls `dogen-signoff.sh` — the HITL gate).
3. **Draft — by direction:** all four directions route to **`dogen-write`**, the sole
   drafting skill. It branches on the declared `intent`:
   - **reference / explanation** — the host agent drafts the page from the signed-off
     plan, stages it, and calls `dogen-record-draft.sh` to record it.
   - **tutorial / how-to** — drafted by *doing*: an evidence-gated step walk that
     captures verbatim proof (output bytes, exit code, SHA-256) via
     `dogen-record-step.sh`, then authors the page from what actually ran (also
     recorded via `dogen-record-draft.sh`).
4. **`dogen-review`** — review the draft alongside its provenance and record a verdict
   (**accept** / **fix** / **redraft**) via `dogen-record-review.sh`. Accept seals
   page SHA-256 hashes; fix/redraft append the note to the steering stream.

The gate is enforced in code, not by convention: `dogen-record-draft.sh` inlines
the gate check and refuses — with no side effects — until a signoff is on record
and the plan hash is current. When you're done, the draft sits in **one local
commit** for you to review and merge. dogen never pushes.

### Confirm your setup works (smoke check)

```bash
# Create a scratch repo:
mkdir /tmp/dogen-smoke && cd /tmp/dogen-smoke && git init -q
git config user.name "Test" && git config user.email "test@example.com"
printf '# Widget API\n\nThe widget API exposes create and delete.\n' > source.md
git add -A && git commit -q -m "seed source"

# Set up a unit:
mkdir -p .dogen/units/smoke
cat > .dogen/units/smoke/unit.md <<'EOF'
---
unit_id: smoke
intent: reference
audience: developers
title: Smoke
sources:
  - path: source.md
sphinx_target: smoke.rst
extra_targets: []
steering_notes: ""
---
# Smoke
EOF

# Run the gate (the scripts must be on your PATH from step 1):
dogen-signoff.sh smoke
echo "# Smoke API" > /tmp/smoke-draft.rst
dogen-record-draft.sh smoke /tmp/smoke-draft.rst
dogen-record-review.sh smoke --verdict accept --note "smoke test"
```

If every script exits 0 and `docs/smoke.rst` exists, your environment is wired up. The ledger
at `.dogen/units/smoke/ledger.md` records the full audit trail. Clean up: `rm -rf /tmp/dogen-smoke`.

### Vocabulary

- **sealed** — a unit whose latest review is an **accept**. Sealed status is derived from the
  ledger's `## reviews` section.
- **ledger** — the plain-markdown audit trail at `.dogen/units/<id>/ledger.md` (replaces the
  old `provenance.yaml`). Records signoff, steering, generations, reviews, and steps.
- **gate** — the signoff act recorded by `dogen-signoff.sh`. `dogen-record-draft.sh`
  checks it inline before recording any draft.

---

## The deterministic scripts

| Script | What it enforces | Exit codes |
|---|---|---|
| `dogen-signoff.sh <id> [--force]` | HITL gate: SHA-256 of `unit.md` + commit; lazy-creates ledger; validates unit-id against path traversal | 0 ok, 1 double-signoff, 2 bad input |
| `dogen-record-draft.sh <id> <file> [--model M]` | Inline gate check + WR-03: ledger before page; identical-redraft check; path-traversal validation | 0 ok, 1 gate fail, 2 bad input, 3 identical, 4 evidence incomplete (unresolved steps) |
| `dogen-record-review.sh <id> --verdict accept\|fix\|redraft [--note N]` | Records verdict; accept seals page SHA-256; fix/redraft appends note to steering stream | 0 ok, 1 no generation, 2 bad input |
| `dogen-record-step.sh <id> <step> --evidence-file F` | Evidence micro-gate: validates verdict enum, requires SHA-256 + exit_code + step_text_sha256; fail stays unverified; staleness check | 0 ok, 1 incomplete, 2 bad input, 3 stale |

Every state-changing script emits one local git commit with `Dogen-Unit:` / `Dogen-Phase:`
trailers (plus `Dogen-Draft:` / `Dogen-Verdict:` / `Dogen-Step:` where relevant), so
`git log --grep 'Dogen-Unit: <id>'` replays a unit's whole path.

---

## Develop dogen itself

The deterministic layer is bash; the test suite is bash.

```bash
# Run the script tests (74 assertions across 32 tests):
bash tests/test_dogen_scripts.sh

# Lint shell scripts:
shellcheck scripts/dogen-*.sh

# Lint skill frontmatter + tool-surface:
python scripts/skill_lint.py
```

### Architecture

```
skills/                          ← the human-facing surface (SKILL.md)
├── dogen-fetch/SKILL.md
├── dogen-plan/SKILL.md
├── dogen-write/SKILL.md
└── dogen-review/SKILL.md

scripts/                         ← the deterministic enforcement layer
├── dogen-common.sh              ← shared helpers (SHA-256, ledger ops, path validation, commit)
├── dogen-signoff.sh             ← HITL gate: hash unit.md, lazy-create ledger, commit "signoff"
├── dogen-record-draft.sh        ← inline gate check + WR-03: ledger before page, commit "draft"
├── dogen-record-review.sh       ← record verdict (accept seals / fix|redraft appends steering), commit "review"
└── dogen-record-step.sh         ← evidence micro-gate, commit "step"
```

See [`docs/middle-path-plan.md`](./docs/middle-path-plan.md) for the full implementation plan
with feature mapping, and [`docs/before-after.md`](./docs/before-after.md) for a concise
comparison of the old (CLI + Python core) and new (scripts + skills) architectures.

### Drill eval harness (deferred)

Skill compliance is measured by a Drill-style eval harness (tmux-driven sessions, LLM-judged
verifier) — outlined in the [plan](./docs/middle-path-plan.md#8-drill-eval-harness--outline-implementation-deferred),
implementation deferred to a subsequent phase.

## Licensing

The core scripts are licensed under **LGPL-3.0-only** (see [`LICENSE`](./LICENSE)). The
portable skills under [`skills/`](./skills/) are licensed separately under **Apache-2.0**
(see [`skills/LICENSE`](./skills/LICENSE)).
