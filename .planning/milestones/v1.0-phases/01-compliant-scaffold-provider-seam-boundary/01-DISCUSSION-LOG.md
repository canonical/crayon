# Phase 1: Compliant Scaffold & Provider-Seam Boundary - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-19
**Phase:** 1-Compliant Scaffold & Provider-Seam Boundary
**Areas discussed:** OSS license, Copyright holder, License granularity, Hot-swap extent, Adapter depth, Seam enforcement, Guardrail proof, Package identity, Coding-guide handling, CI scope + Python matrix, Repo hygiene files, Docs toolchain timing, Dependency management, Coding-guide artefacts

---

## OSS license

| Option | Description | Selected |
|--------|-------------|----------|
| GPL-3.0-or-later | Canonical craft house style; strong copyleft | (initial) |
| Apache-2.0 | Permissive + patent grant; adoption-friendly | |
| LGPL-3.0-or-later | Copyleft on framework, not importers | |

**User's choice:** GPL — initially `GPL-3.0-or-later`, then **corrected to `GPL-3.0-only`** after the Licensing policy was read (policy mandates "not 'v3 or later'"). Library-vs-tool reconfirmed as tool/"everything else" → `GPL-3.0-only`.
**Notes:** Policy reserves Apache for charms; deviations need CEO approval.

---

## Copyright holder

| Option | Description | Selected |
|--------|-------------|----------|
| Canonical Ltd. | Standard for Canonical-owned projects | ✓ |
| Individual author | Personal/non-Canonical work | |

**User's choice:** Canonical Ltd. **Notes:** User then supplied the Licensing policy as authoritative reference; year = year of first publication = 2026.

---

## License granularity

| Option | Description | Selected |
|--------|-------------|----------|
| Single license for now | One license everywhere; add content license later | ✓ |
| Split now: docs CC-BY-SA-4.0 | Separate docs license from commit 1 | |
| Split now: + CC0 for config/data | Most granular | |

**User's choice:** Single license for now.

---

## Hot-swap extent

| Option | Description | Selected |
|--------|-------------|----------|
| Design property (clean boundary) | Swap = new adapter; no runtime selection in P1 | ✓ |
| Runtime-selectable now | Config/env provider switch built now | |
| Third-party pluggable | Entry-point plugin discovery | |

**User's choice:** Design property. **Notes:** User flagged wanting a strict coding guide here too (handled separately).

---

## Adapter depth

| Option | Description | Selected |
|--------|-------------|----------|
| Empty boundary (defer SDK dep) | Adapter shape only; no SDK dependency yet | ✓ |
| Real pinned SDK dep + minimal import | SDK live from commit 1 | |

**User's choice:** Empty boundary.

---

## Seam enforcement

| Option | Description | Selected |
|--------|-------------|----------|
| Static AST check (no install) | AST check flags imports outside adapter | ✓ |
| import-linter (contracts) | Declarative; wants SDK installable | |
| Both (AST now + import-linter later) | Belt-and-suspenders | |
| tach (Rust boundary tool) | Newer alternative | |

**User's choice:** Static AST check. **Notes:** import-linter noted as the Phase-2 upgrade.

---

## Guardrail proof (SC4)

| Option | Description | Selected |
|--------|-------------|----------|
| Committed negative test | Fixture asserts the guard flags a bad import every build | |
| One-time manual demo | Demonstrate once, capture log as evidence | ✓ |
| Doc note only | Describe the guard, no proof test | |

**User's choice:** One-time manual demo. **Notes:** AST check remains the standing CI protection; committed negative-test deferred as optional hardening.

---

## Package identity

| Option | Description | Selected |
|--------|-------------|----------|
| I'll provide the name | User supplies dist + import name | ✓ |
| Working name: docdraft | Build-under placeholder | |
| Placeholder, rename before release | Obviously-temporary name | |

**User's choice:** `dogen` (distribution + import name).

---

## Coding-guide handling

| Option | Description | Selected |
|--------|-------------|----------|
| Wire gates now, apply guide's rules | ruff + type-check in CI from commit 1 | ✓ |
| Scaffold only; enforce as code lands | Defer gates to Phase 2 | |
| Defer entirely to the guide | Decide after guide provided | |

**User's choice:** Wire gates now. **Notes:** User later directed: read the Handbook, synthesize a stricter project coding guide (special attention to the AI-coding critique), and produce AI coding artefacts for agents.

---

## CI scope + Python matrix

| Option | Description | Selected |
|--------|-------------|----------|
| >=3.12, CI on 3.12 (+3.13) | Matches 3.12 target; forward-compat insurance | ✓ |
| >=3.11, CI on 3.11 & 3.12 | Broadest floor (SDK floor) | |
| >=3.13 only | Newest only | |

**User's choice:** >=3.12, CI on 3.12 (+3.13). **Notes:** Bundled defaults accepted — pytest harness stood up now; pre-commit mirrors gates; GitHub Actions. Type checker = `ty` (Astral), per the Handbook.

---

## Repo hygiene files

| Option | Description | Selected |
|--------|-------------|----------|
| Standard set, Canonical conventions | README, CONTRIBUTING, SECURITY, COC, .editorconfig, .gitignore | ✓ |
| Minimal | README + .gitignore + LICENSES only | |
| I'll specify the template set | Point to Canonical templates | |

**User's choice:** Standard set, Canonical conventions. **Notes:** CONTRIBUTING references the Canonical CLA.

---

## Docs toolchain timing

| Option | Description | Selected |
|--------|-------------|----------|
| Defer to Phase 2 | No Sphinx/RTD skeleton in Phase 1 | ✓ |
| Stand up skeleton now | docs/ + conf.py + .readthedocs.yaml | |
| Minimal placeholder only | docs/ dir + RTD stub | |

**User's choice:** Defer to Phase 2.

---

## Dependency management

| Option | Description | Selected |
|--------|-------------|----------|
| Commit uv.lock; defer the bot | Lockfile now; update bot in Phase 2 | ✓ |
| uv.lock + Renovate now | Bot from commit 1 | |
| uv.lock + Dependabot now | GitHub-native bot from commit 1 | |

**User's choice:** Commit uv.lock; defer the bot. **Notes:** Pin-watching matters in Phase 2 when the SDK/CLI pins exist (issue #1606).

---

## Coding-guide artefacts (post-Handbook)

| Option | Description | Selected |
|--------|-------------|----------|
| Full recommended set | coding-guide.md + AGENTS.md + provenance snippet | ✓ |
| Guide + AGENTS.md only | Skip standalone provenance snippet | |
| Coding guide only | Defer agent artefacts | |

**User's choice:** Full recommended set. **Notes:** Produced `.planning/refs/coding-guide.md`, root `AGENTS.md`, `.planning/refs/synthetic-code-provenance.md`. License classification reconfirmed `GPL-3.0-only` in the same turn.

---

## Claude's Discretion

- Exact `ruff` ruleset + `ty` strictness flags (within coding-guide constraints); `tests/` layout.
- Sub-layout within `src/dogen/` (`core/`, `adapters/copilot/`, `cli/`) per ARCHITECTURE.md.
- Wording/structure of README, SECURITY.md, CODE_OF_CONDUCT (Canonical conventions).

## Deferred Ideas

- Runtime/config provider selection; `DraftingProvider` port + mock swap proof → Phase 2 (SEAM-03/04).
- Real `github-copilot-sdk` dep + pinned CLI + smoke test → Phase 2 (SKEL-05).
- `import-linter` upgrade for seam enforcement → Phase 2.
- Committed negative-test for the guardrail → optional future hardening.
- Docs/content license (CC-BY-SA-4.0) → when docs land.
- Sphinx/MyST + RTD docs toolchain → Phase 2.
- Dependency-update bot → Phase 2.
- Third-party plugin/entry-point provider discovery → v2 / non-goal.
