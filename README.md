# dogen

**dogen** is a skills-first, agentic **documentation-drafting** framework for Technical
Authors. It drafts review-ready, **Sphinx-publishable** documentation (MyST Markdown or
reStructuredText, Diátaxis-structured) from human-pointed sources — human-in-the-loop — and
deliberately stops at the boundary of a single traceable local commit.

This iteration is a **pure-skills architecture**: portable Agent Skills (`SKILL.md`) are the
surface a Technical Author drives, backed by a thin layer of deterministic bash scripts that
enforce the load-bearing guarantees (HITL gate, provenance ordering, evidence verification,
accept sealing). No Python, no CLI, no venv — just skills + scripts.

- **Skills-first surface** — the portable `dogen-plan` / `dogen-write` / `dogen-review`
  skill family is the primary, harness-agnostic human interface.
- **Deterministic gates** — 4 bash scripts enforce the HITL gate, write ordering,
  identical-redraft suppression, evidence verification, and structured review
  recording (accept/fix/redraft). The model cannot bypass them.
- **Type-aware drafting**, steered by human intent, audience, and product expertise.
- **Sphinx-publishable output** — the target docs-as-code stack is GitHub + Read the Docs +
  Sphinx, structured along Diátaxis.
- **Zero Python install** — drop `scripts/` + `skills/` into any repo; works in any harness
  that reads `SKILL.md` and exposes `Bash` + `Write`.

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

From the root of your docs repo:

```bash
# Copy the deterministic scripts onto your PATH (or reference them by path):
cp scripts/dogen-*.sh /usr/local/bin/   # or: export PATH="$PWD/scripts:$PATH"

# Install the skills into your harness:
# Claude Code:
cp -r skills/dogen-* .claude/skills/

# GitHub Copilot CLI:
cp -r skills/dogen-* .github/skills/

# opencode:
cp -r skills/dogen-* .opencode/skills/
```

The skills are the interface; the scripts are the deterministic enforcement layer. Your agent
harness sees the three `SKILL.md` files and invokes the scripts via `Bash` as needed.

### 2 — Add context files (recommended)

Context files teach dogen your house style, vocabulary, and where facts live. They land in
`.dogen/context/`:

```bash
mkdir -p .dogen/context
cp path/to/your-style-guide.md .dogen/context/doc-style.md
cp path/to/glossary.md .dogen/context/glossary.md
```

Well-known names the skills look for: `doc-style.md`, `glossary.md`, `structure.md`,
`code-to-docs-map.md`, `doc-gaps.md`.

### 3 — Draft a documentation unit

Drive the skills in order from your agent. They call the deterministic scripts and enforce
the human-in-the-loop gate at each step.

1. **`dogen-plan`** — declare a unit and its sources, shape the outline, record your intent
   and audience, and **sign the plan off** (calls `dogen-signoff.sh` — the HITL gate).
2. **Draft — by direction:** all four directions route to **`dogen-write`**, the sole
   drafting skill. It branches on the declared `intent`:
   - **reference / explanation** — the host agent drafts the page from the signed-off
     plan, stages it, and calls `dogen-record-draft.sh` to record it.
   - **tutorial / how-to** — drafted by *doing*: an evidence-gated step walk that
     captures verbatim proof (output bytes, exit code, SHA-256) via
     `dogen-record-step.sh`, then authors the page from what actually ran (also
     recorded via `dogen-record-draft.sh`).
3. **`dogen-review`** — review the draft alongside its provenance and record a verdict
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

# Run the gate:
scripts/dogen-signoff.sh smoke
echo "# Smoke API" > /tmp/smoke-draft.rst
scripts/dogen-record-draft.sh smoke /tmp/smoke-draft.rst
scripts/dogen-record-review.sh smoke --verdict accept --note "smoke test"
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
# Run the script tests (58 assertions across 21 tests):
bash tests/test_dogen_scripts.sh

# Lint shell scripts:
shellcheck scripts/dogen-*.sh

# Lint skill frontmatter + tool-surface:
python scripts/skill_lint.py
```

### Architecture

```
skills/                          ← the human-facing surface (SKILL.md)
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
