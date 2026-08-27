# dogen: before & after

## What changes

| Aspect | Before (CLI + Python core) | After (scripts + skills) | Why |
|---|---|---|---|
| **Install** | `uv tool install` + Python 3.12 + venv | Scripts onto `PATH` (once); skills into `.agents/skills/` (project) or `~/.agents/skills/` (global) | Zero Python runtime for the consumer |
| **Interface** | Typer CLI (`dogen unit new`, `dogen signoff`, …) | 3 `SKILL.md` files + 4 bash scripts | Skills are the surface; scripts are the teeth |
| **Provenance** | `provenance.yaml` (Pydantic v2, schema v2, 40+ fields) | `ledger.md` (plain markdown, pipe-delimited rows, canonical blank-line separation) | Human-readable; survives compaction; no migration needed |
| **HITL gate** | `SignoffRequiredError` in `orchestrator.py` | `dogen-signoff.sh` computes SHA-256; `dogen-record-draft.sh` refuses inline | Gate stays in deterministic code, not prose |
| **Draft recording** | `draft` in orchestrator (WR-03 ordering in Python) | `dogen-record-draft.sh` writes ledger before page | Same guarantee, ~100 lines of bash |
| **Review recording** | `review` in orchestrator seals hashes / appends steering | `dogen-record-review.sh` handles all 3 verdicts structurally | fix/redraft is deterministic, not prose |
| **Provider model** | Driver (Copilot SDK) + Passenger (host agent) | Passenger only — host agent is always the drafter | The host agent you're talking to IS the agent; no headless session needed |
| **Provider seam** | `DraftingProvider` port + `seam_check.py` + import-linter | Not applicable (no driver) | Nothing to swap; the seam's purpose disappears |
| **Observability** | OTel API in `core/` + logfire in `obs/` | The ledger IS the observability record | No telemetry infra; the audit trail is on disk |
| **Tests** | 57 pytest files (gate, ordering, routing, seam, CLI) | 1 bash test file (65 assertions across 27 tests) + Drill evals (deferred) | Scripts are unit-tested; skill behavior is eval-measured |
| **Codebase size** | ~6000 lines Python (core + adapters + CLI + compose) | ~645 lines of bash (4 gate scripts + shared helpers) + 3 SKILL.md | ~89% reduction in deterministic code |

> **Skill family folded:** the former `dogen-record` skill is folded into `dogen-write`,
> which is now the sole drafting skill and branches on the declared `intent` — reference and
> explanation author straight from sources; tutorial and how-to walk an evidence-gated step
> plan. The evidence gate moved out of prose into `dogen-record-draft.sh` (exit 4 on
> unresolved actionable steps).

## What's preserved (structurally)

- **HITL gate** — `dogen-signoff.sh` refuses re-signoff; `dogen-record-draft.sh` refuses draft without signoff or on stale plan hash
- **Evidence macro-gate** — `dogen-record-draft.sh` refuses an actionable (tutorial/how-to) draft while any step is `unverified` (exit 4), including the missing/empty step-plan cases
- **WR-03 write ordering** — `dogen-record-draft.sh` writes the ledger row *before* copying the page
- **Identical-redraft suppression** — `dogen-record-draft.sh` compares SHA-256 and no-ops on match
- **Evidence micro-gate** — `dogen-record-step.sh` validates verdict enum, requires SHA-256 + exit_code + step_text_sha256; fail stays unverified; staleness check
- **Structured review recording** — `dogen-record-review.sh` handles accept (seals hashes) / fix / redraft (appends steering); note required for fix/redraft
- **Path-traversal protection** — all scripts validate `unit_id` against `../` and `/`
- **Commit trailers** — every script emits `Dogen-Unit:` / `Dogen-Phase:` / `Dogen-Draft:` / `Dogen-Verdict:` / `Dogen-Step:` trailers; staging limited to `.dogen/` + `docs/`
- **Passenger honesty (T-03-03)** — automatically preserved; no driver mode to impersonate
- **Diátaxis routing** — skills route on declared intent (all four directions → dogen-write; tutorial/how-to take the evidence-walk branch)
- **`unit.md` format** — unchanged; YAML frontmatter + body
- **`.dogen/` layout** — unchanged directory structure

## What's lost

- **Schema validation** — no Pydantic; the ledger is plain markdown. Malformed rows are possible.
- **Derived state on read** — `derive_progress()`, `is_sealed()` become skill-level grep heuristics, not computed properties.
- **Multi-owner lease (D-04)** — `resolve_owners()` becomes best-effort grep across ledgers; no atomic lease check.
- **`--json` contract** — no CLI, no structured output. Skills read the ledger directly.
- **Driver mode** — no headless Copilot SDK session. The host agent is always the drafter.
- **Multi-file units** — scripts handle single `sphinx_target` only; `extra_targets` is ignored.
- **57 pytest files** — replaced by 65 bash assertions for scripts + deferred Drill evals for skills.
- **`dogen status` / `unit ls` / `unit show`** — become skill-level ledger reads, not CLI verbs.

## What's gained

- **Zero Python install** — scripts on `PATH` + skills in `.agents/skills/`; works in any agent that reads `SKILL.md`
- **Human-readable provenance** — `ledger.md` is plain markdown with canonical blank-line separation; a TA can read and debug it
- **Compaction recovery** — ledger's first line (`# dogen ledger — unit: <id>`) is the recovery anchor
- **~89% less deterministic code** — ~645 lines of bash vs ~6000 lines of Python
- **Faster iteration** — rubric/review changes are markdown edits, not Pydantic model changes + test suite + release
- **Cross-harness portability** — no Python dependency; works wherever `SKILL.md` + `Bash` + `Write` exist

## Pros & cons

| | Pros | Cons |
|---|---|---|
| **Simplicity** | ~645 lines of bash; anyone can read the scripts | No schema validation; malformed ledger rows possible |
| **Install** | Scripts to `PATH`, skills to `.agents/skills/` — no Python, no venv, no `uv` | Scripts must be on `PATH` (skills invoke them by bare name) |
| **Gate enforcement** | SHA-256 + exit codes + path validation are structural | Routing, lease checks, and coverage checks are prose-enforced |
| **Testability** | Scripts are unit-tested (65 assertions across 27 tests) | Skill behavior needs Drill evals (deferred investment) |
| **Portability** | Any agent that reads the `.agents/skills/` convention (or `SKILL.md`) | Loses the Typer CLI fallback for power users / CI |
| **Provenance** | Human-readable markdown ledger in canonical blank-line format | No v0→v2 migration; no derived state on read |
| **Driver mode** | Removed — simpler, no SDK dependency | Can't batch-draft headlessly; host agent must be present |
