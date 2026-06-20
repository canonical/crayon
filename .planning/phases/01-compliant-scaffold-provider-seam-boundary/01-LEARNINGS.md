<!--
SPDX-FileCopyrightText: 2026 Canonical Ltd.
SPDX-License-Identifier: GPL-3.0-only
-->
<!-- REUSE-IgnoreStart -->
---
phase: 1
phase_name: "compliant-scaffold-provider-seam-boundary"
project: "Agentic Documentation Drafting Framework"
generated: "2026-06-20"
counts:
  decisions: 8
  lessons: 6
  patterns: 6
  surprises: 6
missing_artifacts:
  - "UAT.md"
---

# Phase 1 Learnings: compliant-scaffold-provider-seam-boundary

## Decisions

### GPL-3.0-only as the OSS license, fetched not hand-pasted
The distributable core is licensed GPL-3.0-only. The license text was fetched via `uvx reuse download GPL-3.0-only` into `LICENSES/GPL-3.0-only.txt`, with a top-level `LICENSE` copy (Canonical policy D-05), and the SPDX identifier `GPL-3.0-only` is the single source consumed by the template, sidecars, and `pyproject.toml`.

**Rationale:** Canonical's licensing system of record mandates GPL-3.0-only, the populated `LICENSES/` dir, and the top-level `LICENSE`. Fetching the canonical SPDX text (rather than hand-pasting) guarantees byte-correct, REUSE-recognized license text and avoids transcription drift (RESEARCH "Don't Hand-Roll").
**Source:** 01-01-PLAN.md / 01-01-SUMMARY.md

### Per-file REUSE headers via a committed Jinja2 template, not a REUSE.toml
Annotation is per-file: a custom `.reuse/templates/canonical.jinja2` reproduces the full coding-guide section 7 Canonical notice block byte-for-byte and stamps every file at creation time. The original plans explicitly prohibited any `REUSE.toml` bulk-mapping (D-04).

**Rationale:** D-04 mandates the full per-file Canonical notice on each source file rather than a bulk aggregate map, so each distributable file is self-describing. The template makes the full block reproducible and is itself annotated via a `.license` sidecar (so Jinja2 does not interpret a header inside its own body).
**Source:** 01-01-PLAN.md / 01-01-SUMMARY.md

### spdx copyright-prefix to emit SPDX-FileCopyrightText (no literal "Copyright")
The template and all `reuse annotate` invocations use `--copyright-prefix spdx`, producing `SPDX-FileCopyrightText: 2026 Canonical Ltd.` with no leading literal "Copyright" word.

**Rationale:** The `spdx-string`/`string` prefixes wrongly inject the word "Copyright" (RESEARCH Pitfall 2). The SPDX-FileCopyrightText form is the REUSE-canonical, machine-parseable shape required for the notice block to match coding-guide section 7 exactly.
**Source:** 01-01-PLAN.md / 01-01-SUMMARY.md

### Hexagonal src-layout with adapters/copilot/ as the sole sanctioned import site
The package is `src/dogen/` with `core/` (pure domain, zero vendor imports), `adapters/` + `adapters/copilot/` (the seam boundary — the only place the Copilot SDK may ever be imported), and `cli/` (empty stub, no entrypoint/Typer this phase). Built on hatchling + uv + the src layout.

**Rationale:** Confines the swappable provider behind a single narrow adapter so swapping to OpenCode/Pydantic-AI is not a rewrite; the inward-only dependency rule keeps the core provider-agnostic. hatchling + uv + src-layout is the 2026 packaging golden path and isolates the importable package from the repo root.
**Source:** 01-02-PLAN.md / 01-02-SUMMARY.md

### Pure-stdlib AST seam guardrail, not regex/grep
`scripts/seam_check.py` is the SEAM-02 control: pure stdlib (`ast`/`sys`/`pathlib`), walking every `.py` under `src/dogen` except `adapters/copilot/`, flagging `ast.Import` (incl. aliased), `ast.ImportFrom` (incl. submodules), and `importlib.import_module(...)` by string constant. No third-party deps and no SDK install (D-08/D-09).

**Rationale:** An AST walk resists aliasing, submodule, and `import_module`-by-constant evasion that a regex/grep gate would miss (D-09). Pure stdlib keeps the gate runnable without installing the SDK and survives the Phase-1 "no real SDK dependency" constraint.
**Source:** 01-02-PLAN.md / 01-02-SUMMARY.md

### No real github-copilot-sdk dependency in Phase 1 (D-08)
The `adapters/copilot/` package exists as the designated sole-importer shape but is empty of the SDK; neither `pyproject.toml` nor `uv.lock` references `github-copilot-sdk`. The wheel and lockfile are asserted SDK-free.

**Rationale:** Establishing the seam shape and its enforcement before any drafting logic lets the licensing/packaging/swappability invariants be proven first, and it eliminates the issue-#1606 (CLI auto-update breaks transport) supply-chain vector for the whole of Phase 1.
**Source:** 01-02-PLAN.md / 01-02-SUMMARY.md

### Single-source the seam check across pytest, CI, and pre-commit; commit uv.lock
`tests/test_seam.py` imports `scripts/seam_check.py` and calls the same `main()` the CI step and the pre-commit hook invoke — one implementation, no drift. `uv.lock` is committed (D-18) with a `uv.lock.license` sidecar.

**Rationale:** A duplicated check would let the test and the gate diverge silently; single-sourcing guarantees the pytest test, the CI build gate, and the local hook all enforce the identical invariant. Committing `uv.lock` makes the dev-tool supply chain reproducible and pinned.
**Source:** 01-02-PLAN.md / 01-04-PLAN.md / 01-02-SUMMARY.md

### SHA-pinned first-party GitHub Actions, least-privilege token, ty as a hard gate
CI (`ci.yml`) runs the D-13 gate suite (reuse lint -> ruff check -> ruff format --check -> ty check -> seam check -> pytest -> uv build) on a 3.12+3.13 matrix with `permissions: contents: read`, no secrets, and only `actions/checkout` + `astral-sh/setup-uv` pinned to commit SHA. The ty step is a plain `ty check` (no gate-silencing flag); the documented beta fallback is `continue-on-error` + a tracked issue, never a checker swap (D-14).

**Rationale:** SHA-pinning and least-privilege harden the CI supply chain; running `reuse` via `uvx` (not a reuse GitHub action) keeps CI and pre-commit on one resolved version. Keeping ty a hard gate without `--exit-zero` preserves the type-discipline invariant even while ty is in beta.
**Source:** 01-04-PLAN.md / 01-04-SUMMARY.md

---

## Lessons

### Static type-checkers can't follow a runtime sys.path single-source import
`tests/test_seam.py` imports `seam_check` via a runtime `sys.path.insert`. `ty` resolves imports statically and could not find `scripts/seam_check.py`, failing the D-14 type gate with `unresolved-import`. Fixed by adding `extra-paths = ["scripts"]` under `[tool.ty.environment]` so the static resolver finds the module without duplicating the check logic into the test.

**Context:** Auto-fixed blocking issue during plan 02 Task 3. The single-source pattern (test imports the real script) collides with static analysis, which needs the path declared in config rather than discovered at runtime.
**Source:** 01-02-SUMMARY.md

### Manual line-wrapping fights ruff format in a CI format-check gate
Hand-wrapping lines in `seam_check.py` to satisfy E501 produced code that `ruff format --check .` (a D-13 CI gate) would reformat, which would fail the build. Fixed by running `ruff format` and letting the formatter own line breaks (the wraps collapsed once em-dashes were replaced with ASCII hyphens).

**Context:** Auto-fixed bug during plan 02 Task 3. With `ruff format --check` as a standing gate, any manual formatting must match the formatter's canonical output, so the formatter — not the author — should decide wrapping.
**Source:** 01-02-SUMMARY.md

### `reuse annotate --style ini` is not a valid style; use `--style python` for `#` comments
The plan called for an "INI-style `#`" inline header on `.editorconfig`, but `reuse annotate --style ini` errors (`'ini' is not one of ...`). `--style python` emits byte-identical `#`-prefixed comment lines.

**Context:** Auto-fixed blocking issue during plan 03 Task 2. `reuse`'s comment-style names do not map 1:1 to file types; the comment character (`#`) is what matters, and `python` is the style that produces it.
**Source:** 01-03-SUMMARY.md

### A whole-repo `reuse lint` gate also lints committed `.planning/` meta
Prior plans treated `.planning/` as out-of-REUSE-scope, but the plan-04 CI gate runs `reuse lint` unscoped across the whole repo. `.planning/` (44 tracked files, `commit_docs: true`) and `.claude/CLAUDE.md` are git-tracked and therefore linted; 37 carried no REUSE info, so the gate (and the LIC-01 "whole-repo green" criterion) failed until a meta-scoped `REUSE.toml` was added.

**Context:** Auto-fixed blocking issue during plan 04 Task 2. "Out of scope" is only true if files are untracked; anything committed is in `reuse lint`'s scope, forcing the very `REUSE.toml` the earlier plans had prohibited.
**Source:** 01-04-SUMMARY.md / 01-04-PLAN.md

### The seam guardrail's evasion-resistance has real gaps before the adapter lands
Code review found three correctness gaps that undercut the "AST-based, resists evasion" docstring claim: relative-import handling ignores `node.level`, causing both a false negative (`from . import copilot` slips through — `ImportFrom.names` is never inspected) and a false positive (`from .copilot import Foo`, a local sibling import, is wrongly flagged); `find_violations` has no exception handling, so a syntax/encoding error crashes the gate with an uncaught traceback and exit 1, violating the documented 0/1/2 contract; and `__import__(...)` / variable-argument dynamic imports are not caught. None are blockers while `adapters/copilot/` is intentionally empty (D-08), but they must be fixed before the real adapter lands — exactly when the gate must be trustworthy.

**Context:** Plan-04 code review (4 warnings, 6 info, 0 critical). The gate is sound for plain/aliased/submodule absolute imports it was tested against, but its threat-model claims outrun its implementation for relative, malformed, and `__import__`-based forms.
**Source:** 01-REVIEW.md

### `reuse` version is pinned by comment only in CI, risking CI/pre-commit drift
Pre-commit pins `fsfe/reuse-tool` to `v6.2.0`, but CI runs `uvx reuse lint` with no version constraint and `reuse` is not in `uv.lock`. The inline comment asserts uvx pins the same version, but nothing enforces it — when fsfe ships a newer `reuse`, CI silently runs a different linter than local hooks, breaking the "identical gate, no drift" guarantee (D-13). The fix is to pin explicitly (`uvx reuse@6.2.0 lint`) or add `reuse==6.2.0` to the dev group so it is captured in `uv.lock`.

**Context:** Plan-04 code review (WR-04). The single-source intent held for the seam check (one script) but not for `reuse`, where CI and pre-commit resolve the version through different, unsynchronized mechanisms.
**Source:** 01-REVIEW.md

---

## Patterns

### Per-file REUSE annotation via a committed Jinja2 template + spdx prefix
A custom `.reuse/templates/canonical.jinja2` reproduces the full notice block byte-for-byte and is applied with `reuse annotate --copyright "Canonical Ltd." --year 2026 --license GPL-3.0-only --copyright-prefix spdx --template canonical <file>`. The template iterates `copyright_lines` and `spdx_expressions` so it never degrades to the bare two-SPDX-line default.

**When to use:** Any repo that must be REUSE-compliant from commit 1 with a full org notice block (not just bare SPDX tags) on every distributable source file.
**Source:** 01-01-PLAN.md / 01-01-SUMMARY.md

### `.license` sidecars for files that can't carry an inline header
Use a `<file>.license` sidecar (carrying the full notice block) for files where an inline header is hazardous or impossible: the Jinja2 template itself (self-interpretation), generated lockfiles (`uv.lock` — never hand-edit a header in), `.md` docs, and `.gitignore` (keeps the ignore file clean). Inline headers are used where the comment syntax is safe (`.py`, `pyproject.toml`, `ci.yml`, `.editorconfig`).

**When to use:** When inline annotation would be interpreted by the file's own tooling, would corrupt a generated artifact, or would clutter a config file — the sidecar is the verified path.
**Source:** 01-01-SUMMARY.md / 01-03-SUMMARY.md

### Single-source one check across pytest test, CI step, and pre-commit hook
Write the check once as a runnable script (`scripts/seam_check.py`); the pytest test imports and calls its `main()`, the CI step runs `python scripts/seam_check.py`, and the pre-commit local hook runs the same script with `pass_filenames: false`. No logic is duplicated, so the three enforcement points cannot drift.

**When to use:** Any invariant you want enforced identically in tests, CI, and local commit hooks — author it as one importable/executable unit, never three copies.
**Source:** 01-02-PLAN.md / 01-04-PLAN.md / 01-02-SUMMARY.md

### AST guardrail with a self-anchored scan root and a non-vacuous exit code
Resolve the scan root from the script's own `__file__` location (not a bare relative path) so CI's cwd can't make it scan nothing, and return a distinct non-zero exit (2) when zero files are found — a misconfigured scan must error, not silently pass. Return 0 clean, 1 on violation (naming file:line).

**When to use:** Any CI guardrail that walks a directory tree, where a "found nothing -> passed" vacuous success would be a dangerous false green (RESEARCH Pitfall 4).
**Source:** 01-02-PLAN.md / 01-02-SUMMARY.md

### Meta-only REUSE.toml at aggregate precedence to keep per-file headers winning
When committed non-source meta (`.planning/**`, `.claude/**`) must satisfy a whole-repo `reuse lint` but should not carry inline per-file notices, add a `REUSE.toml` scoped only to those globs at `precedence = "aggregate"`. REUSE precedence rules mean per-file inline headers on real source still override it, so the per-file policy (D-04) is preserved for source while the bulk gate goes green.

**When to use:** When a whole-repo license-lint gate trips on tracked docs/meta that legitimately should not be annotated inline — bulk-annotate only those dirs and rely on precedence to leave source untouched.
**Source:** 01-04-SUMMARY.md / 01-VERIFICATION.md

### REUSE-Ignore comments to suppress false-positive SPDX tags in prose
Planning docs that quote the SPDX license-identifier tag in prose, verify commands, or template examples are misread by `reuse` as real declarations. Wrap the file body (after the YAML frontmatter) in REUSE-Ignore HTML comments — `reuse`'s own documented mechanism — which render invisibly and leave content unchanged.

**When to use:** Any Markdown/doc that mentions SPDX tags as text rather than as an actual license declaration, in a repo gated by whole-repo `reuse lint`.
**Source:** 01-04-SUMMARY.md / 01-04-PLAN.md

---

## Surprises

### A plain-language comment can trip the plan's own literal-string grep gate (twice)
Plan verification used literal-string greps (`! grep -q "OSI Approved"`, `! grep -q "exit-zero"`) as negative gates. Innocuous explanatory comments containing those exact phrases ("no OSI Approved classifier", "Do NOT add --exit-zero") made the gates fail even though the prohibited thing did not exist. Both were fixed by rewording the comments to drop the literal token while keeping the warning's intent.

**Impact:** Two separate auto-fixed bugs (plan 02 in `pyproject.toml`, plan 04 in `ci.yml`). Established a recurring class: negative grep gates collide with documentation that names the thing being prohibited, forcing comment rewordings rather than real code changes.
**Source:** 01-02-SUMMARY.md / 01-04-SUMMARY.md

### `reuse` parses SPDX tags quoted in prose as real license declarations
After the meta `REUSE.toml` fix, the whole-repo lint still failed with 10 "Invalid SPDX License Expression" hits — all from five prior planning artifacts that quote `SPDX-License-Identifier: GPL-3.0-only` inside prose, verify commands, and the Jinja2 template example. `reuse` treats any line containing the tag as a real declaration.

**Impact:** Required wrapping five `.planning/` docs in REUSE-Ignore markers to get `reuse lint` to exit 0 (DEF-02-01 class). This drift recurs: the plan-04 handoff had to warn that any future planning doc quoting an SPDX tag must wrap it or the whole-repo gate goes red again.
**Source:** 01-04-SUMMARY.md / 01-VALIDATION.md

### The "no REUSE.toml" prohibition had to be reversed because `.planning/` is git-tracked
Plans 01-01/01-02 explicitly prohibited a `REUSE.toml` (D-04, per-file only). But because `.planning/` and `.claude/` files are committed, the unscoped CI `reuse lint` gate linted them, and a meta-scoped `REUSE.toml` became unavoidable to reach LIC-01 whole-repo green — directly contradicting the earlier prohibition.

**Impact:** A plan-level prohibition was overturned mid-phase; ratified later (Security escalation F2) as the accepted interpretation of D-04 (meta-only `REUSE.toml`, per-file headers still win by precedence). Shows a stated invariant ("no REUSE.toml ever") can be infeasible once tracked meta enters the lint scope.
**Source:** 01-04-SUMMARY.md / 01-SECURITY.md

### The Phase-1 "SDK-free, #1606 eliminated" security disposition did not survive Phase 2
Phase 1's threat disposition claimed the no-SDK-dependency stance *eliminated* the issue-#1606 (CLI auto-update breaks transport) vector. The retroactive security audit found `github-copilot-sdk==1.0.2` is now a pinned runtime dependency, so the #1606 vector is back in scope — the "eliminated" claim is true only for the Phase-1 window.

**Impact:** Security escalation F1, ratified as accepted with re-mitigation handed to the Phase-2 threat model. A point-in-time security disposition was carried as if permanent; the audit had to explicitly stop it being carried forward as still-true.
**Source:** 01-SECURITY.md

### The whole-repo LIC-01 lint gate is currently RED despite a "passed" verification
`01-VERIFICATION.md` recorded `reuse lint` green at 67/67 files. The later validation/security passes found the standing whole-repo gate now exits 1 on 4 "Invalid SPDX Expression" hits — in Phase-2 planning prose and `01-VERIFICATION.md` itself, which quote SPDX tags without REUSE-Ignore wrapping. The per-file annotation control (122/122, Missing=0, Bad=0) is intact; only doc prose drifts.

**Impact:** LIC-01's automated *mechanism* exists and runs every commit, but the gate's actual exit status flipped red after verification, tracked as Phase-2 housekeeping debt (DEF-02-01/02) rather than a Phase-1 coverage gap. The verification report became part of the problem it had certified clean.
**Source:** 01-VALIDATION.md / 01-SECURITY.md

### No UAT artifact and ty's runtime-vs-static mismatch were both quietly absorbed
There is no `UAT.md` for Phase 1 — all success criteria were mechanically verifiable, so verification was tool-execution-only with no human/conversational UAT round. Separately, the single-source seam-test pattern only worked once `ty` was given `extra-paths = ["scripts"]`, an accommodation the static checker needed that the runtime import did not.

**Impact:** Phase 1 closed 4/4 verified with zero UAT, confirming a pure-compliance-scaffold phase can skip conversational UAT. The ty accommodation is a standing config dependency: remove `extra-paths` and the type gate breaks even though the tests still pass.
**Source:** 01-VERIFICATION.md / 01-02-SUMMARY.md
<!-- REUSE-IgnoreEnd -->
