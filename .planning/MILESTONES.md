# Milestones

## v1.1 Live Copilot Path Hardening (Shipped: 2026-06-22)

**Delivered:** Pure brownfield hardening of the live `dogen draft --provider copilot` path — closing the four gaps the first real live run surfaced so the loop runs end-to-end out of the box on an available model of any family and records honest, observed provenance. No net-new domain features.

**Phases completed:** 2 phases, 3 plans, 7 tasks
**Timeline:** 2026-06-22 (1 day)
**Git range:** `365b3bb` → `a74dd32` (44 commits)
**Code:** +1,420/−58 across 14 src/test files; suite now 131 passing (was 97 at v1.0)
**Requirements:** 7/7 v1.1 requirements satisfied (LIVE-01/02/03, ERR-01/02, PROV-01/02 — zero unsatisfied, zero orphaned)
**Verification:** green fake-SDK unit suite + operator-approved D-24 manual live runs (manual-only path, out of CI by design)

**Key accomplishments:**

- **Operator-selectable model with an available default** — retired the hardcoded, unavailable `gpt-5`; `gpt-5-mini` is the new default and a `--model` flag is threaded through `select_provider` to the Copilot adapter (the mock path stays SDK-free). *(LIVE-01)*
- **Non-interactive source reads work** — a `PermissionHandler.approve_all` handler auto-approves the read-only `grep`/`glob`/`view` allowlist, safe by construction (write/exec/network remain denied). *(LIVE-02)*
- **Any model family drafts** — `reasoning_effort` is family-gated (sent to GPT-5 family, omitted for Claude models that reject it), so selecting a Claude model no longer errors on the parameter. *(LIVE-03)*
- **Clean live error mapping** — a backend model rejection raises `ModelRejectedError` naming the requested model and exits nonzero; every other JSON-RPC/`ProcessExitedError` (draft *and* status path) maps to a handled `BackendUnavailableError` — never a raw traceback. This **closes accepted v1.0 tech-debt item #4** (the raw `JsonRpcError` traceback on model rejection). *(ERR-01, ERR-02)*
- **Honest observed provenance** — a pure `tool_events_to_provenance` seam helper plus a `get_events()` observation in `_run_draft` fill `context_origins` (view-read paths, kept distinct from human-pointed `sources`) and `tools_used` (`builtin:<name>`) from observed `TOOL_EXECUTION_START` events, first-seen de-duped and honestly empty when nothing ran. Completes the BL-01 honesty arc (v1.0 stopped *fabricating*; v1.1 *truthfully fills*). *(PROV-01, PROV-02)*

**Carried tech debt (cosmetic, CI green):** SKEL-02 tags-only requirements bookkeeping (v1.0) — still open, deferred.

Known deferred items at close: 0 (see STATE.md Deferred Items).

---

## v1.0 MVP (Shipped: 2026-06-20)

**Delivered:** The thinnest end-to-end proof of the Mode-A drafting loop — an agent drafts one human-pointed unit into Sphinx-publishable MyST, writing the F1 audit/provenance surface and stopping before any commit — on top of the three foundations that are expensive to retrofit (a CI-enforced multi-provider seam, SDK-independent observability, and REUSE-compliant licensing).

**Phases completed:** 2 phases, 8 plans, ~20 tasks
**Timeline:** 2026-06-19 → 2026-06-20 (2 days)
**Git range:** `0a377d8` → `24bf4d7` (85 commits, 16 `feat`)
**Code:** ~4,800 LOC Python (2,861 src / 1,942 tests), 97 tests passing
**Requirements:** 23/23 v1 requirements satisfied (zero unsatisfied, zero orphaned)

**Key accomplishments:**

- **REUSE-compliant from commit 1** — SPDX license + copyright on every file, GPL-3.0-only core (CC-BY-SA-4.0 for published docs/content), `LICENSES/` populated, and `reuse lint` enforced as a CI gate. *(LIC-01, LIC-02)*
- **Provider-seam boundary, CI-enforced** — the Copilot SDK is confined to a single `adapters/copilot/` module; a declarative import-linter contract (upgraded from the Phase-1 AST guardrail) fails the build on any `copilot`/`logfire`/`opentelemetry.sdk` import reaching `core/`. *(SEAM-01, SEAM-02, SEAM-03, SEAM-04)*
- **End-to-end drafting loop** — `dogen unit new → steer → draft → review` produces Sphinx-publishable MyST and stops before any commit, with a bounded read-only toolset (grep/glob/view allowlist; write/exec/network denied). Proven live on both the deterministic mock and the real pinned `github-copilot-sdk==1.0.2`, with "backend unavailable" handled as a non-crashing `BackendUnavailableError`. *(SKEL-01..05)*
- **F1 planning-directory schema v0** — per-unit `unit.md` / draft / `provenance.yaml` / `progress.yaml` persisted on disk with `schema_version: 0`, full provenance (model/version/effort, tooling + SDK version, context origins distinct from human-pointed sources, tools, reviewer edits), a `pending → sourced → drafted → reviewed → committed` lifecycle that stops at `committed`, and structurally-reserved (possibly-empty) verification-evidence fields. *(PLAN-01..07)*
- **Provable HITL gate** — the orchestrator refuses to draft a unit unless intent + audience steering was recorded first ("no recorded steering → no draft"), capturing author + timestamp so an audit shows no substantial draft without a human steering input (AC5 evidence). *(HITL-01, HITL-02)*
- **SDK-independent observability** — the loop emits traces/metrics/logs through a provider-independent OTel-API layer in the core (not the SDK's own telemetry), wired to a concrete local backend, with each run's `run_id` correlating to its `provenance.yaml` generation entry. *(OBS-01, OBS-02, OBS-03)*

**Known gaps (accepted as tech debt, do not turn CI red):**

- **SKEL-02 bookkeeping** — `02-04-SUMMARY.md` records SKEL-02 only in `tags:`, not a machine-readable requirements key. Requirement is verified satisfied (real `sphinx-build -W` CI job + `tests/test_docs_build.py`); rollup is cosmetic.
- **Live-backend error-mapping breadth** — `dogen draft --provider copilot` can surface a raw `JsonRpcError` traceback when the backend rejects the *model* (vs a clean handled message). The defined "backend unavailable" states are handled and tested; this is error-mapping breadth on the manual-only (D-24) live path deliberately kept out of CI.

Known deferred items at close: 0 (see STATE.md Deferred Items).

---
