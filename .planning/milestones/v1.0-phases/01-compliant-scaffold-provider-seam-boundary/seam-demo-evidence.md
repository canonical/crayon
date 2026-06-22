# Seam-Guardrail Demo Evidence (D-10 / SC4)

**Date (UTC):** 2026-06-19T20:24:48Z
**Requirement:** SEAM-02 / SC4 — "the CI build fails if any Copilot SDK import
appears outside `adapters/copilot/`."
**Decision:** D-10 — the guardrail proof is a **one-time manual demo** (deliberately
misplace an import, observe the check fail, capture the log). No permanently
committed failing fixture; the AST check is the standing CI/pre-commit protection.

This file is the captured evidence of that one-time demo. After capture the demo
files were removed and the tree restored clean and green (verified at the end).

---

## Command under test

```
uv run python scripts/seam_check.py
```

The same `scripts/seam_check.py:main()` is invoked by the CI step
(`.github/workflows/ci.yml`), the pre-commit hook (`.pre-commit-config.yaml`),
and the pytest test (`tests/test_seam.py`) — single source, no drift.

---

## 1. Deliberately misplaced import in the domain core — FAILS (exit 1)

A file containing a single banned import was created at the forbidden location:

```
# src/dogen/core/_demo_violation.py
import copilot
```

Run and captured output (stderr):

```
seam-check: VIOLATION(S):
  /home/artem.konev@canonical.com/Documents/docpr-2845/src/dogen/core/_demo_violation.py:1: import copilot
```

**Exit code: 1** — the build would fail. The check names the exact `file:line`
and the offending import. This is the SC4 evidence: a misplaced Copilot import
outside `adapters/copilot/` fails the seam gate.

---

## 2. The SAME import inside the sanctioned adapter — PERMITTED (exit 0)

The identical `import copilot` line was placed at the one sanctioned site:

```
# src/dogen/adapters/copilot/_demo_allowed.py
import copilot
```

With the core/ violation removed and only the adapter file present, the run and
captured output (stdout):

```
seam-check: OK - 4 files, no vendor imports outside adapters/copilot/
```

**Exit code: 0** — the adapter subtree is excluded from the scan, so the same
import that fails in `core/` is allowed here. The "4 files" count excludes the
adapter demo file, confirming `adapters/copilot/` is the designated sole-importer
boundary (SEAM-01).

(Intermediate run with BOTH files present still reported only the `core/`
violation and exited 1 — the adapter file was never flagged.)

---

## 3. Cleanup — tree restored clean and green (no committed fixture, D-10)

Both demo files were removed:

- `src/dogen/core/_demo_violation.py` — removed
- `src/dogen/adapters/copilot/_demo_allowed.py` — removed

Final verification run and captured output (stdout):

```
seam-check: OK - 4 files, no vendor imports outside adapters/copilot/
```

**Exit code: 0** — the tree is clean; no permanently-failing seam fixture remains
(the D-10 trade-off: a one-time manual demo, not a committed negative test). The
standing protection is the AST check wired into CI and pre-commit on every build.

---

## Summary

| Scenario | Location | Exit | Result |
|----------|----------|------|--------|
| `import copilot` in domain core | `src/dogen/core/_demo_violation.py` | 1 | VIOLATION named (SC4 evidence) |
| `import copilot` in sanctioned adapter | `src/dogen/adapters/copilot/_demo_allowed.py` | 0 | Permitted (SEAM-01 boundary) |
| Both demo files removed | — | 0 | Tree clean, no committed fixture (D-10) |

SC4 satisfied: the seam guardrail was observed catching a deliberately-misplaced
Copilot import, the evidence is captured here, and the repository ends clean and
green.
