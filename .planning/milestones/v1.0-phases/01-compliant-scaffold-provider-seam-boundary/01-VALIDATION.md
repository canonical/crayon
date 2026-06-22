<!--
SPDX-FileCopyrightText: 2026 Canonical Ltd.
SPDX-License-Identifier: GPL-3.0-only
-->
<!-- REUSE-IgnoreStart -->
---
phase: 01
slug: compliant-scaffold-provider-seam-boundary
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-20
---

# Phase 1 — Validation Strategy

> Per-phase validation contract. Reconstructed retroactively (State B) from PLAN/SUMMARY
> artifacts and the live test tree, then gap-filled. Phase 1 already passed goal
> verification 4/4 (`01-VERIFICATION.md`); this document records the *automated, repeatable*
> coverage behind each requirement and closes the two checks that were previously
> manual-only.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x (`pytest-asyncio`), plus stdlib AST guardrail + `import-linter` + `uvx reuse lint` command gates |
| **Config file** | `pyproject.toml` → `[tool.pytest.ini_options]` (`testpaths = ["tests"]`) |
| **Quick run command** | `uv run pytest -q tests/test_seam.py tests/test_seam_violation_detected.py tests/test_smoke.py` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~2 s (pytest suite); the LIC-02 wheel test adds a `uv build` (~a few seconds) |

---

## Sampling Rate

- **After every task commit:** Run the quick command (seam + smoke).
- **After every plan wave:** Run the full suite (`uv run pytest -q`).
- **Standing CI/pre-commit gates (every push & commit):** `uvx reuse lint` → `ruff check` → `ruff format --check` → `ty check` → `scripts/seam_check.py` → `pytest` → `uv build` (D-13 order, `ci.yml`).
- **Max feedback latency:** < 5 seconds locally for the pytest layer.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01 | 01 | 1 | LIC-01, LIC-02 | — | Canonical REUSE template + GPL-3.0-only LICENSES/ present; every file annotatable | command | `uvx reuse lint` | ✅ | ⚠️ see note |
| 01-02 | 02 | 1 | SEAM-01 | T-02-02 | `dogen.core` / `cli` import no `copilot` / `github_copilot_sdk` | unit | `uv run pytest -q tests/test_seam.py tests/test_seam_importlinter.py` | ✅ | ✅ green |
| 01-02 | 02 | 1 | LIC-02 | T-02-SC | built wheel METADATA carries `License-Expression: GPL-3.0-only` | integration | `uv run pytest -q tests/test_wheel_license_metadata.py` | ✅ | ✅ green |
| 01-02 | 02 | 1 | SEAM-02 (pass path) | T-02-02 | guardrail green on the clean tree (exit 0) | unit | `uv run pytest -q tests/test_seam.py` | ✅ | ✅ green |
| 01-04 | 04 | 1 | SEAM-02 (failure path) | T-04-03 | guardrail **detects** a misplaced Copilot import in every banned form (aliased / submodule / `import_module`-by-constant) | unit | `uv run pytest -q tests/test_seam_violation_detected.py` | ✅ | ✅ green |
| 01-04 | 04 | 1 | LIC-01 | T-03-03 / T-04-04 | whole-repo `reuse lint` exits 0 — every tracked file carries SPDX info | command | `uvx reuse lint` | ✅ | ⚠️ see note |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flagged*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. Two gaps closed during this
retroactive validation (converting one-time manual checks into standing regression tests):

- [x] `tests/test_seam_violation_detected.py` — SEAM-02 **failure path**: drives
  `seam_check.find_violations` against synthetic violation files in `tmp_path`
  (hermetic — never touches the real `src/` tree), parametrized over all five banned
  import forms plus a clean-file negative control. Replaces the one-time D-10
  `seam-demo-evidence.md` manual demo with a repeatable test.
- [x] `tests/test_wheel_license_metadata.py` — LIC-02: builds the wheel with
  `uv build --wheel` into `tmp_path` and asserts `License-Expression: GPL-3.0-only` in
  `*.dist-info/METADATA`. Replaces the manual `unzip … | grep License` verification step.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| SC4 one-time D-10 seam misplacement demo | SEAM-02 | Historical, point-in-time evidence captured during execution; now superseded by `test_seam_violation_detected.py` for standing coverage | See `seam-demo-evidence.md` (archival; no longer the primary verification). |

*All Phase-1 requirements now have automated verification. The row above is retained for
provenance only — its behavior is automated by Wave 0 above.*

---

## Known Issues / Flags

- **⚠️ Whole-repo `uvx reuse lint` is currently RED (4 invalid SPDX expressions).** The
  failures are in planning `.md` prose that quotes `SPDX-License-Identifier:` without
  `REUSE-IgnoreStart/End` wrappers — `01-VERIFICATION.md` (this phase) and three Phase-2
  docs (`02-01-SUMMARY.md`, `02-02-SUMMARY.md`, `deferred-items.md`). This is the exact
  drift `01-04-SUMMARY.md`'s handoff warned about. **No source, test, hygiene, or CI file
  is affected**, and the two tests added here are clean. LIC-01's automated verification
  *mechanism* (the standing `reuse lint` gate) exists and runs every commit — this is a
  content-drift fix (wrap the four files), tracked separately, not a Nyquist coverage gap.
  Cleanest owner: Phase 2's own validate/secure pass.

---

## Validation Sign-Off

- [x] All requirements have automated verify (`<automated>` test or standing command gate)
- [x] Sampling continuity: no 3 consecutive requirements without automated verify
- [x] Wave 0 covers all previously-MISSING references (SEAM-02 failure path, LIC-02 metadata)
- [x] No watch-mode flags
- [x] Feedback latency < 5 s (pytest layer)
- [x] `nyquist_compliant: true` set in frontmatter
- [ ] Whole-repo `reuse lint` green — blocked by pre-existing planning-doc drift (see Flags)

**Approval:** approved 2026-06-20 (Nyquist coverage); LIC-01 lint-content flag tracked separately.

## Validation Audit 2026-06-20

| Metric | Count |
|--------|-------|
| Gaps found | 2 |
| Resolved | 2 |
| Escalated | 0 |
<!-- REUSE-IgnoreEnd -->
</content>
</invoke>
