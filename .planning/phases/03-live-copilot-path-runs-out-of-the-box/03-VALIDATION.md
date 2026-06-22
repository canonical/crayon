---
phase: 3
slug: live-copilot-path-runs-out-of-the-box
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-22
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `03-RESEARCH.md` §Validation Architecture. The live path is
> manual-only (D-24, no token/network in CI); every automated assertion runs
> against the established `_StubClient` fake SDK
> (`monkeypatch.setattr("dogen.adapters.copilot.provider.CopilotClient", factory)`).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`, `testpaths = ["tests"]`) |
| **Quick run command** | `uv run pytest tests/test_copilot_*.py -x` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | ~10–20 seconds (no network) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_copilot_*.py -x` (the adapter test cluster)
- **After every plan wave:** Run `uv run pytest` (full suite — includes seam guardrails + import-linter test)
- **Before `/gsd-verify-work`:** Full suite green, `uv run lint-imports`, and `python scripts/seam_check.py` clean; **plus** the manual live runs for success criteria 1–3 (D-24, off-CI)
- **Max feedback latency:** ~20 seconds (automated); manual live run separate

---

## Per-Task Verification Map

> Task IDs are assigned by the planner. This map is keyed by requirement until
> PLAN.md exists; the planner lifts each row into per-task `<verify>` blocks.

| Req | Wave | Behavior | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists |
|-----|------|----------|------------|-----------------|-----------|-------------------|-------------|
| LIVE-01 | 1 | `CopilotDraftingProvider()` default model is `gpt-5-mini`; `select_provider("copilot", model="x")` forwards `model` | — | N/A | unit | `uv run pytest tests/test_copilot_model_selection.py -x` | ❌ W0 |
| LIVE-01 | 1 | `select_provider("mock", model="x")` ignores model, imports no SDK | — | mock path stays SDK-free (D-25) | unit | `uv run pytest tests/test_seam.py tests/test_copilot_model_selection.py -x` | ⚠️ extend seam test |
| LIVE-02 | 1 | `create_session` called with `on_permission_request=PermissionHandler.approve_all` | T-02.3-01/02 | auto-approve only ever sees read-only tools | unit (assert kwarg) | `uv run pytest tests/test_copilot_session_kwargs.py -x` | ❌ W0 |
| LIVE-03 | 1 | GPT-5 model → `reasoning_effort` present; Claude model → `reasoning_effort` is `None`/absent | — | N/A | unit (parametrized) | `uv run pytest tests/test_copilot_session_kwargs.py -x` | ❌ W0 |
| ERR-01 | 1 | fake `JsonRpcError(-32603, 'Model "x" is not available')` → `ModelRejectedError` naming `self._model` | leak/DoS | clean message, exit nonzero, no traceback | unit | `uv run pytest tests/test_copilot_error_mapping.py -x` | ❌ W0 |
| ERR-02 | 1 | fake `JsonRpcError(-32603, 'Directory path must be absolute')` AND non-`-32603` `JsonRpcError` → `BackendUnavailableError` (NOT `ModelRejectedError`) | leak/DoS | handled failure, exit nonzero | unit (parametrized) | `uv run pytest tests/test_copilot_error_mapping.py -x` | ❌ W0 |
| ERR-01/02 | 1 | CLI renders both errors as exit-1 clean messages (Typer `CliRunner`, mock provider that raises) | leak/DoS | nonzero exit, curated message | unit | `uv run pytest tests/test_cli_draft_errors.py -x` | ❌ W0 |
| D-08 | 0 | Regression: `from copilot._jsonrpc import JsonRpcError` succeeds and is the class the adapter catches | DoS (SDK bump) | error handling fails loudly, not silently | unit | `uv run pytest tests/test_copilot_jsonrpc_import.py -x` | ❌ W0 |
| V4 guard | 1 | `tools.py` `READONLY == {grep, glob, view}` and `DENY` names unchanged | T-02.3 | allowlist cannot quietly broaden | unit | `uv run pytest tests/test_copilot_toolset_boundary.py -x` | ❌ W0 |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Extend `_StubClient` (in `tests/test_copilot_backend_unavailable.py` or a shared `conftest.py` fixture) so its `create_session(self, **kwargs)` **captures** `self.session_kwargs = kwargs` and returns a stub session context manager whose `send_and_wait` returns a scripted `assistant.message` event — the shared harness all new kwargs/error tests build on
- [ ] `tests/test_copilot_model_selection.py` — LIVE-01 (default `gpt-5-mini` + `select_provider` threading + mock ignores)
- [ ] `tests/test_copilot_session_kwargs.py` — LIVE-02 + LIVE-03 (assert `on_permission_request` present; `reasoning_effort` present for GPT-5 / `None` for Claude)
- [ ] `tests/test_copilot_error_mapping.py` — ERR-01 + ERR-02 (fake `JsonRpcError` injection; `-32603`-overload disambiguation)
- [ ] `tests/test_cli_draft_errors.py` — CLI exit-code rendering (Typer `CliRunner`)
- [ ] `tests/test_copilot_jsonrpc_import.py` — D-08 private-import regression guard
- [ ] `tests/test_copilot_toolset_boundary.py` — V4 assertion that `READONLY`/`DENY` are unchanged (guards `approve_all` safety)

*Every new test file carries the full GPL-3.0-only SPDX header block (coding-guide §7; `reuse lint` gates CI).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| A real written Sphinx-publishable draft on the new default | LIVE-01 (criterion 1) | Needs a live Copilot token/account, absent from CI (D-24) | On the dev machine: `dogen steer <unit>` then `dogen draft <unit> --provider copilot` (bare, no `--model`) → a `.md` draft is written |
| Source-grounded draft with auto-approved reads | LIVE-02 (criterion 2) | Live, non-interactive run required | Live `dogen draft --provider copilot` on a unit pointing at real sources → draft is grounded in them, not a refusal/ask-to-paste |
| Claude-family model drafts without a parameter error | LIVE-03 (criterion 3) | Live run on a Claude model | `dogen draft <unit> --provider copilot --model claude-sonnet-4.5` → a written draft, no `reasoning_effort` rejection |

*Automated coverage proves the wiring (kwargs/error mapping); the manual runs prove the live end-to-end result.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (the shared `_StubClient` extension + 6 new test files)
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
