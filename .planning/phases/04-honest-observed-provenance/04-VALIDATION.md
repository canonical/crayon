---
phase: 4
slug: honest-observed-provenance
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-22
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio (async drafting loop) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest -q tests/test_copilot_provenance.py` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~15–30 seconds (no network; live Copilot path is manual-only, D-24) |

---

## Sampling Rate

- **After every task commit:** Run the quick command for the touched test module.
- **After every plan wave:** Run `uv run pytest -q` (full suite).
- **Before `/gsd-verify-work`:** Full suite must be green; `reuse lint` + `ruff` + type-check gates green.
- **Max feedback latency:** 30 seconds.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| _populated during planning/execution_ | | | PROV-01 / PROV-02 | T-02.3-03 / — | provenance reflects only observed reads/tools; never fabricated, never `sources` | unit | `uv run pytest -q tests/test_copilot_provenance.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_copilot_provenance.py` — fake-SDK (`_StubClient` emitting `TOOL_EXECUTION_START` events) + pure `mapping.py` helper unit tests for PROV-01/02 (criterion 4)
- [ ] Existing `tests/conftest.py` shared fixtures cover SDK-free collection (reuse as-is — keep collection SDK-free)

*Existing pytest infrastructure otherwise covers all phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| A real live draft populates `provenance.yaml` `context_origins` (the `view`-read source path) and `tools_used` (`builtin:*`), distinct from `sources` | PROV-01, PROV-02 | Live Copilot path is manual-only (D-24) — no token/network in CI | Run `dogen draft --provider copilot` on a unit with sources; inspect the unit's `provenance.yaml` `generations[]` for non-empty `context_origins`/`tools_used`; confirm the live CLI `view` arg key matches the bundled-schema `path` (RESEARCH open question A1) |

*All CI-runnable behaviors have automated verification via the fake-SDK test.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
