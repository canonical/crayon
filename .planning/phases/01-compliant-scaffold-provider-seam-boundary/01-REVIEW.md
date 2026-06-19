---
phase: 01-compliant-scaffold-provider-seam-boundary
reviewed: 2026-06-19T00:00:00Z
depth: standard
files_reviewed: 20
files_reviewed_list:
  - scripts/seam_check.py
  - src/dogen/__init__.py
  - src/dogen/adapters/__init__.py
  - src/dogen/adapters/copilot/__init__.py
  - src/dogen/cli/__init__.py
  - src/dogen/core/__init__.py
  - tests/__init__.py
  - tests/test_seam.py
  - tests/test_smoke.py
  - pyproject.toml
  - .github/workflows/ci.yml
  - .pre-commit-config.yaml
  - .reuse/templates/canonical.jinja2
  - .editorconfig
  - .gitignore
  - README.md
  - CONTRIBUTING.md
  - SECURITY.md
  - CODE_OF_CONDUCT.md
  - LICENSE
findings:
  critical: 0
  warning: 4
  info: 6
  total: 10
status: issues_found
---

# Phase 1: Code Review Report

**Reviewed:** 2026-06-19
**Depth:** standard
**Files Reviewed:** 20
**Status:** issues_found

## Summary

This is a deliberately near-empty compliance scaffold. The bulk of the surface
(empty `__init__.py` markers, license text, OSS-hygiene markdown, REUSE
template, editorconfig) is correct and free of defects. The only file carrying
real logic is `scripts/seam_check.py` (SEAM-02), and that is where every
substantive finding lives.

The seam guardrail is well-constructed for its primary job — it correctly
catches plain, submodule, and aliased absolute imports of `copilot` /
`github_copilot_sdk`, including imports nested inside function bodies and
`if TYPE_CHECKING:` blocks (AST walk is recursive). It correctly rejects
substring/prefix false positives (`copilotx`, `copilot_sdk_helpers` are NOT
flagged), and the `0/1/2` exit-code contract is sound *for the cases it
handles*. The `import_module("copilot")` constant-string detection works as
documented.

However the guardrail has three correctness gaps that undermine the "AST-based,
resists evasion" claim in its own docstring, plus one robustness gap that breaks
the documented exit-code contract. None rise to BLOCKER because the seam is an
accident-prevention gate over a subtree that is *intentionally empty* this phase
(D-08, no real SDK dependency), so there is no live vendor import to leak today.
But these should be fixed before the adapter actually lands, because that is
exactly when the gate must be trustworthy.

No security vulnerabilities, no hardcoded secrets, no injection surfaces. CI is
least-privilege (`contents: read`) and SHA-pins its actions.

## Warnings

### WR-01: Relative-import handling is wrong — both false negative and false positive

**File:** `scripts/seam_check.py:105-108`
**Issue:** The `ImportFrom` branch ignores `node.level` (the relative-import
depth) and only looks at `node.module`. Two concrete defects result:

1. **False negative.** `from . import copilot` parses to
   `module=None, level=1, names=['copilot']`. The guard
   `node.module and _is_banned(node.module)` short-circuits on `module=None`,
   and the imported *name* in `node.names` is never inspected. So a re-export
   such as `from . import copilot` (or `from .adapters import copilot`) inside
   core/cli would slip through. The `ast.Import` branch checks `alias.name`,
   but `ast.ImportFrom` never checks its `names` at all.
2. **False positive.** `from .copilot import Foo` parses to
   `module='copilot', level=1`. Because `level` is discarded, `_is_banned`
   sees the bare string `"copilot"` and flags it — even though this is a
   *local relative* import of a sibling module, not the vendor package. If any
   non-adapter package ever contains a local module literally named `copilot`,
   the gate fires a spurious VIOLATION.

**Fix:**
```python
elif isinstance(node, ast.ImportFrom):
    # Relative imports (level > 0) are never the external vendor package.
    if node.level == 0 and node.module and _is_banned(node.module):
        hits.append((node.lineno, f"from {node.module} import ..."))
    # Catch `from . import copilot` / `from pkg import copilot` re-exports.
    elif node.level == 0 and node.module is None:
        hits += [
            (node.lineno, f"from . import {a.name}")
            for a in node.names
            if _is_banned(a.name)
        ]
```
(Also consider flagging `from <pkg> import copilot` where the imported *name*
is a banned top-level — e.g. `from somewhere import copilot` — depending on how
strict the invariant must be.)

### WR-02: Unparseable source crashes the gate and violates the 0/1/2 exit contract

**File:** `scripts/seam_check.py:96, 114-142`
**Issue:** `find_violations` calls `ast.parse(path.read_text(...))` with no
exception handling. A file with a syntax error (or a non-UTF-8 byte) raises
`SyntaxError` / `UnicodeDecodeError`, which propagates out of `main`,
terminating the process with an uncaught traceback and exit code 1. The
docstring promises a disciplined contract: `0` clean, `1` violation, `2`
misconfig. A broken-but-vendor-clean file is neither a violation nor a scan-root
misconfig, yet it reports as exit 1 (indistinguishable from a real seam
violation) with a stack trace. Worse, if a refactor ever makes this gate run
*before* ruff in some context, it becomes the thing that surfaces syntax errors
— with the wrong exit semantics.

**Fix:** Wrap the parse and route parse failures to a deterministic outcome
(reuse exit code `2` for "cannot analyze", or surface a clear per-file error and
aggregate):
```python
try:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
except (SyntaxError, UnicodeDecodeError) as exc:
    raise SeamCheckError(f"{path}: cannot parse ({exc})") from exc
```
and catch `SeamCheckError` in `main` to `return 2`. Ruff is the syntax gate;
the seam check should fail *cleanly*, not crash.

### WR-03: CI comment claims "first-party actions only" but uses a third-party action

**File:** `.github/workflows/ci.yml:36-39`
**Issue:** The comment on line 36 asserts "First-party actions only, pinned to a
commit SHA (supply-chain: T-04-01)", but line 39 uses
`astral-sh/setup-uv` — an Astral (third-party) action, not a GitHub
`actions/*` org action. The action *is* correctly SHA-pinned (good), so the
supply-chain posture is fine, but the stated invariant is false. Either the
comment is wrong or the policy is being silently violated; both are review
hazards because the next person trusts the comment. This phase's review brief
specifically calls out third-party-action SHA-pinning, so the mischaracterization
matters.

**Fix:** Correct the comment to reflect reality, e.g.:
```yaml
# Actions pinned to commit SHA (supply-chain: T-04-01). astral-sh/setup-uv is
# the one third-party action; vetted and SHA-pinned, not floated by tag.
```

### WR-04: `reuse` version is pinned by comment only, not enforced — drift risk between CI and pre-commit

**File:** `.github/workflows/ci.yml:46-47`, `.pre-commit-config.yaml:24-27`
**Issue:** The pre-commit hook pins `fsfe/reuse-tool` to `rev: v6.2.0`. CI runs
`uvx reuse lint` with no version constraint; the inline comment asserts uvx
"pins the same reuse version (6.2.0)" but nothing enforces that — `uvx reuse`
resolves the latest compatible `reuse` at run time, and `reuse` is not in
`uv.lock` (confirmed: it is invoked via `uvx`, outside the locked dependency
graph). The moment fsfe publishes 6.3.0, CI silently runs a different linter
than local pre-commit, breaking the "identical gate, no drift" guarantee the
comments repeatedly claim (D-13). A stricter future `reuse` could fail CI on
code that passed local hooks, or vice versa.

**Fix:** Pin the version explicitly in CI so the claim is enforced, not
aspirational:
```yaml
- name: REUSE lint
  run: uvx reuse@6.2.0 lint
```
(or add `reuse==6.2.0` to the dev dependency group and run `uv run reuse lint`
so it is captured in `uv.lock` like ruff/ty).

## Info

### IN-01: `__import__` and non-constant dynamic imports bypass the seam gate

**File:** `scripts/seam_check.py:55-80`
**Issue:** `_check_call` only flags `import_module(<str constant>)`. It does not
catch `__import__("copilot")`, nor `importlib.import_module(some_variable)`.
The docstring scopes the claim narrowly ("by string constant"), so this is
honest, but it is worth recording as a known evasion vector for when the adapter
lands. As an accident-prevention gate (not a security sandbox) this is
acceptable; document it as such.
**Fix:** Optionally extend `_check_call` to also match `__import__` by name, and
note in the module docstring that variable-argument dynamic imports are out of
scope by design.

### IN-02: Adapter exemption only covers files *inside* `adapters/copilot/`, not an `adapters/copilot.py` module

**File:** `scripts/seam_check.py:36, 126`
**Issue:** `ADAPTER_DIR in py.parents` exempts only files whose parent chain
contains the `adapters/copilot/` directory. If the seam were ever refactored
from a package to a single-file module (`adapters/copilot.py`), that file would
*not* be exempt and the gate would flag the sanctioned import site itself.
Currently moot (the seam is a package), but brittle to a plausible future
layout change.
**Fix:** Exempt by path-prefix relationship instead, e.g.
`py == ADAPTER_FILE or ADAPTER_DIR in py.parents`, or resolve the sanctioned
site from a small allowlist.

### IN-03: CI triggers on both `push` and `pull_request`, double-running on same-repo PRs

**File:** `.github/workflows/ci.yml:20`
**Issue:** `on: [push, pull_request]` causes two full matrix runs for every PR
that originates from a branch in this repo (one `push` event, one
`pull_request` event). Wasted CI minutes and noisy status checks. (Performance
is out of v1 scope; flagged as Info only.)
**Fix:** Scope `push` to protected branches, e.g.
`on: { push: { branches: [main] }, pull_request: {} }`.

### IN-04: Redundant `.gitignore` entry

**File:** `.gitignore:9-10`
**Issue:** `dist/` (line 9) already ignores everything under it, so
`dist/_wheel/` (line 10) is dead config.
**Fix:** Delete line 10.

### IN-05: `test_smoke.py` import assertion is effectively a tautology

**File:** `tests/test_smoke.py:34-35`
**Issue:** `assert importlib.import_module(name) is not None` cannot fail on its
own merits — `import_module` either returns a module object (never `None`) or
raises `ModuleNotFoundError`. The real assertion is "does not raise", so the
`is not None` adds no signal. Harmless, but it reads as if it tests something it
does not.
**Fix:** Either drop the `is not None` (let the import raise) or assert a
meaningful property (e.g. `mod.__name__ == name`). Not a reliability defect, so
optional.

### IN-06: `tests/test_seam.py` mutates `sys.path` at import time with no cleanup

**File:** `tests/test_seam.py:23`
**Issue:** `sys.path.insert(0, .../scripts)` runs at module import and is never
removed, leaking into the rest of the pytest session. With only one consumer
today this is benign, but a future top-level module named `seam_check`
elsewhere could be shadowed. A conftest fixture or `pyproject` `extra-paths`
(already declared for `ty`) would be cleaner. Not a correctness bug.
**Fix:** Prefer a `tests/conftest.py` path setup or a `pytest` `pythonpath`
setting over per-test `sys.path` mutation.

---

_Reviewed: 2026-06-19_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
