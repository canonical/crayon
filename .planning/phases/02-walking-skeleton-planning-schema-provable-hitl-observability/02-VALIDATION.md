---
phase: 02
slug: walking-skeleton-planning-schema-provable-hitl-observability
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-20
reconstructed_from: artifacts (State B — no prior VALIDATION.md; PLAN/SUMMARY + live suite)
suite: 90 passed
gap_fill:
  - "SEAM-04 (PARTIAL → COVERED): added tests/test_docs_build.py::test_seam_doc_names_alternates locking the doc claim (OpenCode SDK + Pydantic AI named; seam wired into the toctree)"
---

# Phase 02 — Validation Strategy

> Per-phase validation contract, reconstructed retroactively (State B) from the
> four PLAN/SUMMARY pairs and the live test suite, then gap-filled to Nyquist
> compliance. All 19 phase requirements have automated verification.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (+ pytest-asyncio for the async drafting loop) |
| **Config file** | `pyproject.toml` → `[tool.pytest.ini_options]` (`testpaths = ["tests"]`) |
| **Quick run command** | `uv run pytest -q tests/<file>.py` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~1.5 seconds (90 tests) |
| **Adjacent gates** | `uv run lint-imports` (seam contract), `uv run --extra docs sphinx-build -W -b html docs docs/_build` (SKEL-02), `scripts/seam_check.py` (AST seam) |

---

## Sampling Rate

- **After every task commit:** Run the quick command for the touched test file.
- **After every plan wave:** Run `uv run pytest -q` (full suite).
- **Before `/gsd-verify-work`:** Full suite must be green.
- **Max feedback latency:** ~2 seconds (full suite is fast; no watch mode).

---

## Per-Task Verification Map

One row per phase requirement (the validate-phase contract is requirement-centric).
"Plan" is the source plan; "Wave" mirrors the plan number.

| Requirement | Plan | Wave | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|-------------|------|------|------------|-----------------|-----------|-------------------|-------------|--------|
| SKEL-01 | 01 | 1 | — | N/A | unit/cli | `uv run pytest -q tests/test_cli_unit_new.py tests/test_planning_fs.py` | ✅ | ✅ green |
| SKEL-02 | 04 | 4 | — | N/A | integration | `uv run pytest -q tests/test_docs_build.py` (real `sphinx-build -W`) | ✅ | ✅ green |
| SKEL-03 | 02 | 2 | T-02.2-02 | No code path writes `committed` (AST-asserted) | unit (AST) | `uv run pytest -q tests/test_orchestrator_hitl.py::test_orchestrator_never_writes_committed` | ✅ | ✅ green |
| SKEL-04 | 03 | 3 | T-02.3-01/02 | Bounded read-only allowlist; write/exec/network denied | unit | `uv run pytest -q tests/test_copilot_mapping.py::test_toolsets_are_source_qualified_builtins` | ✅ | ✅ green |
| SKEL-05 | 03 | 3 | T-02.3-03/04/SC | Backend-unavailable is handled, never a crash; SDK pinned | unit | `uv run pytest -q tests/test_copilot_backend_unavailable.py tests/test_smoke_harness.py` | ✅ | ✅ green |
| SEAM-03 | 02 | 2 | — | N/A | unit | `uv run pytest -q tests/test_observability_correlation.py -k select_provider tests/test_copilot_backend_unavailable.py::test_provider_satisfies_drafting_port` | ✅ | ✅ green |
| SEAM-04 | 01,03 | 1,3 | — | N/A | unit (content) + seam | `uv run pytest -q tests/test_docs_build.py::test_seam_doc_names_alternates tests/test_seam_importlinter.py` | ✅ | ✅ green |
| PLAN-01 | 01 | 1 | — | `.planning/` write-guard | unit/e2e | `uv run pytest -q tests/test_planning_fs.py tests/test_loop_mock_e2e.py::test_full_loop_reaches_reviewed` | ✅ | ✅ green |
| PLAN-02 | 01 | 1 | — | N/A | unit | `uv run pytest -q tests/test_models.py::test_machine_models_default_schema_version_zero` | ✅ | ✅ green |
| PLAN-03 | 01 | 1 | — | N/A | unit | `uv run pytest -q tests/test_models.py -k "round_trips or distinct or steering_records"` | ✅ | ✅ green |
| PLAN-04 | 02,03 | 2,3 | — | Span/provenance carry no secret | unit | `uv run pytest -q tests/test_orchestrator_hitl.py -k generation tests/test_copilot_mapping.py` | ✅ | ✅ green |
| PLAN-05 | 02 | 2 | — | N/A | e2e | `uv run pytest -q tests/test_loop_mock_e2e.py -k reviewer_edit` | ✅ | ✅ green |
| PLAN-06 | 02 | 2 | T-02.2-02 | Lifecycle stops at `reviewed`; never `committed` | unit | `uv run pytest -q tests/test_orchestrator_hitl.py -k "progress or committed" tests/test_models.py::test_progress_accepts_lifecycle_ordering_in_history` | ✅ | ✅ green |
| PLAN-07 | 01 | 1 | — | N/A | unit | `uv run pytest -q tests/test_models.py -k "reserves_empty or verification_step"` | ✅ | ✅ green |
| HITL-01 | 02 | 2 | T-02.2-01 | Refuse-to-draft has no side effects | unit/e2e | `uv run pytest -q tests/test_orchestrator_hitl.py::test_draft_refuses_without_steering tests/test_loop_mock_e2e.py::test_draft_refuses_without_steer` | ✅ | ✅ green |
| HITL-02 | 02 | 2 | — | Steering provably precedes draft (AC5) | unit/e2e | `uv run pytest -q tests/test_loop_mock_e2e.py::test_steer_records_author_and_precedes_draft tests/test_orchestrator_hitl.py::test_draft_reads_prior_steering_act` | ✅ | ✅ green |
| OBS-01 | 02 | 2 | T-02.2-03 | Core uses OTel API only; no backend import | unit + seam | `uv run pytest -q tests/test_observability_correlation.py -k "no_backend or get_tracer" tests/test_seam_importlinter.py` | ✅ | ✅ green |
| OBS-02 | 02 | 2 | T-02.2-03 | `send_to_logfire=False` (no egress) | unit | `uv run pytest -q tests/test_observability_correlation.py::test_configure_observability_is_idempotent` | ✅ | ✅ green |
| OBS-03 | 02 | 2 | — | N/A | unit | `uv run pytest -q tests/test_observability_correlation.py -k "run_id or exported_span" tests/test_orchestrator_hitl.py::test_draft_writes_correlated_generation` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. pytest + pytest-asyncio
were already installed in Phase 1; this phase added one test
(`tests/test_docs_build.py::test_seam_doc_names_alternates`) to close the SEAM-04
documentation gap — no new framework, config, or fixtures were required.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real Copilot SDK round-trip (live draft against the authenticated CLI) | SKEL-05 | Requires an authenticated Copilot token + network; deliberately kept out of CI (D-24) so the automated suite needs no SDK/token. The harness's argument-handling and backend-unavailable branches *are* automated. | Authenticate the Copilot CLI (`gh-cli` / `COPILOT_GITHUB_TOKEN`), then `DOGEN_SMOKE_LIVE=1 uv run python scripts/smoke_draft.py --unit <id>`. Re-run and re-record `get_status().version` (pin: CLI `1.0.64-0`) before trusting the loop after any SDK/CLI bump. |

---

## Validation Sign-Off

- [x] All requirements have an automated verify command (19/19)
- [x] Sampling continuity: no 3 consecutive requirements without automated verify
- [x] Wave 0 covers all MISSING references (none remained; one PARTIAL filled)
- [x] No watch-mode flags
- [x] Feedback latency < 2s (full suite ~1.5s)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-20

---

## Validation Audit 2026-06-20

| Metric | Count |
|--------|-------|
| Requirements audited | 19 |
| COVERED (pre-audit) | 18 |
| Gaps found | 1 (SEAM-04, PARTIAL) |
| Resolved (test added) | 1 |
| Escalated | 0 |
| Manual-only | 1 (SKEL-05 live SDK smoke — by design, D-24) |

**Gap filled:** `tests/test_docs_build.py::test_seam_doc_names_alternates` — locks
SEAM-04's documentation claim (that `docs/seam.md` names the OpenCode SDK and a
Pydantic AI agent as alternates, and that `seam` stays wired into the published
toctree). The swappability *behavior* was already covered by `select_provider`
dispatch tests, port conformance, and the import-linter seam contract; only the
doc claim lacked an automated lock.

**Out-of-scope observation (non-blocking, pre-existing):** `uv run ty check`
reports one diagnostic at `tests/test_orchestrator_hitl.py:346` (`_FailingDraftStore`
not assignable to `PlanningStore`; the inline `# type: ignore[arg-type]` is not
honoured by `ty`). This file was **not** touched by this validation — it predates
the audit (commit `d343155`) and is unrelated to the Nyquist gap fill. Flagged
here for follow-up; the full pytest suite, ruff, lint-imports, and the Sphinx
`-W` build are all green.
