# AGENTS.md — operating contract for coding agents in `dogen`

This file binds **any** coding agent (Copilot, Claude, or other) working in this repository. It is intentionally short; the full standard is [`.planning/refs/coding-guide.md`](.planning/refs/coding-guide.md), which you must follow.

`dogen` is an agentic documentation-drafting framework: it drafts Sphinx-publishable documentation, steered by a human, and **stops at a singular local commit** — it never pushes, opens PRs, builds, or publishes.

## Non-negotiable invariants

1. **The provider seam is sacred.** The Copilot SDK (`copilot` / `github_copilot_sdk`) may be imported **only** inside `adapters/copilot/`. `core/` has **zero vendor imports** and depends only on the `Protocol` ports it defines. A stray import outside the adapter is a CI failure, not a style nit.
2. **You own what you ship.** If you can't explain what code does and *why*, don't merge it. Synthetic code meets the same bar as hand-written code.
3. **No regressions.** Don't break what worked.

## How to write code here

- **Python 3.12**, tooling fixed to **`ruff`** (lint + format) and **`ty`** (type check), env/deps via **`uv`**. Run them before proposing a change.
- **No `typing.Any`** in signatures or public attributes; annotate every public function fully.
- **Functions ≤ ~60 lines**; low complexity; few exit points; dict-dispatch or ternary over if-else-to-assign.
- **Docstrings** (NumPy style) with params/returns/raises on every public symbol. Comments explain the **why**, never the what.
- **Real data structures** (`@dataclass`, pydantic, enums) over stringly-typed dicts. Loose coupling; small modules.
- **Bash is thin glue only** (`set -euo pipefail`, `[[ ]]`, functions for repeats, `shellcheck`). Logic goes in Python.
- **Tests:** `pytest`/`pytest-asyncio`; mock only at the vendor/IO boundary, never the whole core; deterministic, fresh-context.

## AI-specific discipline

- **Emit provenance** for synthetic code using [`.planning/refs/synthetic-code-provenance.md`](.planning/refs/synthetic-code-provenance.md) (timestamp, harness, model+mode, anatomy, token cost).
- **Review your own generated comments and docstrings** — they're plausible and often wrong.
- **Shell-command allowlists only.** Never assume or request arbitrary shell access; arbitrary shell risks data loss and out-of-bounds writes on user hosts and CI runners. Use file/search tools over shell for discovery.
- **Pick the right tool** — deterministic code beats an LLM for deterministic work.

## Licensing (REUSE, from commit 1)

Every source file carries the full Canonical notice block ending in:

```
# SPDX-FileCopyrightText: 2026 Canonical Ltd.
# SPDX-License-Identifier: GPL-3.0-only
```

License text in `LICENSES/GPL-3.0-only.txt` + top-level `LICENSE`. See `coding-guide.md` §7 for the exact header.

## Branching & commits

`main` is stable and default. Branch as `docpr-<ticket>-<objective>` (kebab-case). Squash-merge, delete on merge, keep PRs small. **Never** push, open PRs, build, or publish on the user's behalf — that boundary is the whole point of this project.
