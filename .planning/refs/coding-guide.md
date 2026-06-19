# dogen coding guide

**Status:** binding for all code in this repository — human- and machine-authored alike.
**Source:** synthesized from Canonical's *Handbook for engineering practice in documentation* (Machine-assisted development, Code rules, Code review practice, Branching). Where this guide is stricter or more specific than the Handbook, this guide wins for `dogen`; where the Handbook adds practice not contradicted here, it still applies.
**Audience:** contributors and any coding agent operating in this repo (see [`AGENTS.md`](../../AGENTS.md)).

The Handbook's framing is the standard we hold to: *"Regardless of where our code comes from, we aren't exempt from correct and safe software development."* Synthetic code is held to **exactly** the same bar as hand-written code, and the author who merges it owns it.

---

## 1. Core rules

1. **You own what you ship.** If you cannot explain what a unit of code does and *why*, it does not merge — no matter what produced it.
2. **No regressions.** A change must not break something that worked before it. This is non-negotiable and is what tests defend.
3. **Functions stay small.** Target ≤ 60 lines (one printed page, one statement per line). A longer function is a decomposition smell, not a length problem.
4. **Comments explain *why*, not *what*.** The code says what. Comments justify the non-obvious decision, the constraint, the trade-off. Delete comments that merely restate the code.
5. **Review every synthetic comment and docstring.** Generated prose is fluent and frequently wrong, benign, or meaningless. Treat it as an unreviewed claim until you've checked it against the code.
6. **Common languages only:** Python and Bash. Don't introduce a third language for glue.

---

## 2. Python standards

**Toolchain (fixed):** `ruff` (lint + format) and `ty` (Astral's type checker) — per the Handbook's mandated Python toolchain. Environments, dependencies, and lockfile via `uv`. Target Python **3.12** (`requires-python = ">=3.12"`).

Every rule below exists to counter a specific weakness observed in synthetic Python. They are enforced by `ruff`/`ty` where a rule exists, and by review otherwise.

| Rule | Counters | Enforcement |
|---|---|---|
| **Precise types; `typing.Any` is banned** in signatures and public attributes. Use concrete types, `Protocol`, `TypedDict`, generics, unions. | "Unnecessarily loose typing" | `ty` strict; `ruff` ANN |
| **Full annotations on every public function/method** — params and return. | loose typing | `ruff` ANN; `ty` |
| **Bounded cyclomatic complexity** and few exit points. Prefer guard clauses + a single meaningful return over scattered returns. | "high cyclomatic complexity", "too many exit points" | `ruff` C901 (max-complexity), PLR |
| **No if/elif ladder to assign one value.** Use a ternary, a dict dispatch, or `match`. | "traditional if-else blocks to assign a single value" | review + `ruff` SIM |
| **Small, cohesive modules and classes.** No monoliths; one responsibility per module. | "monolithic modules and classes" | review |
| **Depend on abstractions, not concretions.** Core depends on `Protocol` ports, never on adapter internals. Keep coupling loose. | "tight coupling between modules, classes, functions" | review + the seam guardrail (§6) |
| **Rule of three for abstraction.** Don't extract a shared helper until the third caller. *But* don't write an inflexible single-use function that just hides a block either — extract for clarity, not ceremony. | "inflexible functions only called once" | review |
| **Use real data structures.** `@dataclass`, `pydantic` models, `enum`, `NamedTuple`, sets/dicts — not ad-hoc parallel lists or stringly-typed dicts. | "aversion to basic data structures" | review |
| **Use idiomatic decorators** where they remove boilerplate: `@dataclass`, `@functools.cached_property`, `@functools.wraps`, `@contextlib.contextmanager`. | "no common decorators" | review |
| **Docstrings on every public module, class, and function**, documenting **params, returns, and raises**. One docstring style repo-wide (NumPy-style); enforced by `ruff` D. | "docstrings lacking parameter and return value descriptions" | `ruff` D (pydocstyle, numpy convention) |
| **Inline comments are rare and load-bearing.** No comment that narrates the next line. | "overuse of inline comments" | review |
| **Dependencies are justified and minimal**, pinned via `uv.lock`. No arbitrary `>=x,<y` constraints picked at random — pin what you import, widen only with a reason. | "arbitrary dependency constraints" | review + `uv.lock` |
| **Don't wrap another language from Python** (no shelling out to do what a library does). | "wrapping other languages" | review |

---

## 3. Bash standards

Bash is for **thin glue only** (CI steps, trivial orchestration). Anything with branching logic, data handling, or edge cases belongs in Python. Lint with `shellcheck`; format with consistent 2-space indent.

- `set -euo pipefail` at the top of every script.
- Use `[[ ... ]]`, never the outdated `[ ... ]`.
- Wrap any repeated sequence of operations in a function (rule of three applies).
- Store a command's output **once** in a variable when reused — don't re-invoke it (it can mutate between calls).
- Comment the *why*, same as Python. No comment-free scripts.
- Keep shell operations readable — no opaque multi-stage `sed`/`awk` chains; reach for Python instead.
- No nonsense operations (`true > file.txt` and similar).
- Don't build output one `echo` per line where a heredoc or single write is clearer.
- Consistent, descriptive, kebab-or-snake directory and file names; no gratuitous nesting.

---

## 4. Testing standards

**Toolchain:** `pytest` + `pytest-asyncio` (the drafting loop is async). Stand the harness up from commit 1, even when there's little to test.

- **Don't over-mock.** Mock only at the true boundary — the vendor adapter and external I/O. Inside the core, use real objects or lightweight fakes that implement a port. Tests that mock everything test the mocks. (Counters "overuse of mocks", "rigid and bespoke testing logic".)
- **Test behaviour, not implementation.** Parametrize over cases instead of copy-pasting near-identical tests.
- **Determinism.** Tests pass with a fresh context, no caching, and in any order. No reliance on wall-clock, network, or test-ordering.
- **Coverage is a signal, not a gate.** High trust in automated checks, but they have "intractable practical and theoretical limitations" — they are part of the picture, never all of it.

---

## 5. Machine-assisted (AI) development

Adoption of coding agents is a company mandate — applied with rigour, not "unchecked excitement." These rules are how we make synthetic code durable and auditable.

- **Author responsibility is absolute.** Generated code merges only when a human understands it and has verified it meets every rule in this guide. "I didn't write it" is never a defence.
- **Emit provenance for synthetic code.** Use the reusable prompt in [`synthetic-code-provenance.md`](synthetic-code-provenance.md): timestamp, harness, model + mode, the full anatomy (skills/instructions/user decisions/prompts/examples), and token cost. (This dev-process record is *separate from* dogen's own product `provenance.yaml`, but deliberately mirrors its shape.)
- **Review generated comments and docstrings** as unverified claims (§1.5).
- **Shell-command allowlists, always.** Any agent skill/tool that can run shell must use an explicit allowlist — never grant arbitrary shell. Agents over-reach to shell for trivial discovery (failing simple globs), and arbitrary shell is a data-loss and out-of-bounds risk on user hosts and CI runners.
- **Choose the right tool.** Before reaching for an agent or LLM, ask: is the task a predictable process with no step variation? High edge-case variability? Does it need near-human text interpretation? Does it need to operate inside the host like a user? Deterministic software beats an LLM for deterministic work.
- **Reusable agent operations** (anything an agent does more than once, e.g. a CI task) must be tested with a **fresh context, no caching**, against **disparate inputs** and **competing-vendor models**, and documented with an example output, full anatomy, harnesses + models tested, observed variation, input data, token cost (cached and uncached), and a test date.
- **Mind guardrails and drift.** Model guardrails are inconsistent (the same task framed differently can pass or refuse), and models drift between versions. Don't assume today's behaviour is stable; pin and re-verify.

---

## 6. Architecture invariants (`dogen`)

These are not style preferences — they are the contract that makes the provider seam real. Violating them is a build failure, not a review nit.

- **Hexagonal / ports-and-adapters. Dependencies point inward only.** `core/` is pure Python with **zero vendor imports**. It depends only on `Protocol` ports it defines.
- **`adapters/copilot/` is the single place the Copilot SDK may be imported.** No `copilot` / `github_copilot_sdk` import appears anywhere else. This is enforced in CI by a static AST check (see Phase 1 plan).
- **Ports are shaped by domain verbs**, not by the SDK's method signatures. A port that mirrors the vendor API has already failed.
- **Scope border:** the framework drafts and stops at a singular local commit. No pushing, PR-opening, building, or publishing logic — ever. (Relevant from Phase 2 onward; stated here as a standing invariant.)

---

## 7. Licensing & file headers

REUSE-compliant from commit 1; `reuse lint` gates CI. Per Canonical's Licensing policy, **every source file carries the full notice block** (not a bare SPDX line):

```python
# This file is part of dogen, an agentic documentation-drafting framework.
#
# SPDX-FileCopyrightText: 2026 Canonical Ltd.
# SPDX-License-Identifier: GPL-3.0-only
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3, as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program. If not, see <http://www.gnu.org/licenses/>.
```

- License text lives in `LICENSES/GPL-3.0-only.txt` (REUSE) plus a top-level `LICENSE` (policy).
- `SPDX-FileCopyrightText:` is used (not a plain `Copyright` line) so `reuse lint` passes cleanly while preserving the policy block.
- Copyright **year = year of first publication** = `2026`. Holder = `Canonical Ltd.`
- Documentation/content license is **deferred** to when real docs land (policy default CC-BY-SA-4.0; confirm against the policy's CC-BY-NC-SA-4.0 inconsistency before first docs ship).
- CLA-contributed files use the policy's "License granted by Canonical Limited" notice variant.

---

## 8. Branching, commits, review

From the Handbook's trunk-based model:

- **`main` is the default branch and stable at all times.** Trunk-based development.
- **Feature branches** live ~one pulse; name them `docpr-<ticket>-<objective>` (kebab-case, alphanumeric, concise), or `<objective>` with no ID when there's no ticket.
- **Squash and merge** by default for a clean history; delete branches on merge.
- Keep PRs small and reviewable — changes over ~1,000 lines aren't viable to review.
- **Two maintainer reviews** before merge; maintainers' own code isn't exempt.
- **Request changes** rather than leaving mixed-signal comments; mark nitpicks explicitly.
- **Manual review, never spot-check:** reviewers check out the code and try the change locally (UX, smoke, cross-platform) — CI is necessary but not sufficient.

---

*This is a living document. Update it as the team's machine-assisted practice matures and as the Handbook's stub sections (Testing, CI, Security policies) are filled in.*
