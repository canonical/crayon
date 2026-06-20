---
phase: 2
phase_name: "walking-skeleton-planning-schema-provable-hitl-observability"
project: "Agentic Documentation Drafting Framework"
generated: "2026-06-20"
counts:
  decisions: 10
  lessons: 9
  patterns: 8
  surprises: 6
missing_artifacts:
  - "UAT.md"
---

# Phase 2 Learnings: walking-skeleton-planning-schema-provable-hitl-observability

## Decisions

### F1 schema_version envelope with reserved-but-empty verification fields
Every machine-readable F1 model (`Unit`, `Provenance`, `Progress`) carries `schema_version: int = 0`, and the verification-evidence fields (`Verification.steps`, `Provenance.reviewer_edits`, plus `VerificationStep.state="unverified"`/`evidence=None`/`env_fingerprint=None`) are present but empty at v0.

**Rationale:** A version envelope makes future migrations explicit and detectable; reserving the verification fields now costs nothing and avoids a breaking schema change later (PLAN-07, D-34).
**Source:** 02-01-SUMMARY.md

### sources vs context_origins kept as two distinct fields (D-37)
`Unit.sources` (human-pointed) and `Generation.context_origins` (agent-read) are modeled as separate fields that never collapse into one; setting one never mutates the other.
**Rationale:** They answer different audit questions — what the operator pointed at vs. what the agent actually read — and conflating them would corrupt the AC5 provenance record.
**Source:** 02-01-SUMMARY.md

### DraftingProvider / SourceLookup / PlanningStore ports shaped by domain verbs
The three `typing.Protocol` ports expose domain verbs (`draft_unit`, `scaffold_unit`, `load_unit`, `write_draft`, `read/write_provenance`, `read/write_progress`) rather than file operations or SDK-mirroring shapes, and carry zero vendor imports.
**Rationale:** A port shaped by the domain keeps the seam Copilot-agnostic (Anti-Pattern 2 avoided), so a new backend is one new adapter behind an unchanged port.
**Source:** 02-01-SUMMARY.md

### Deterministic SDK-free mock provider as the CI proof
`MockDraftingProvider` implements `DraftingProvider.draft_unit` returning a deterministic MyST snippet derived only from inputs (fixed synthetic model/tokens, no wall-clock, no randomness, no SDK import), and `select_provider` defaults to `copilot` but resolves `mock` for CI/tests.
**Rationale:** The whole loop must run deterministically in CI with no Copilot token or network so the skeleton is always demoable and the real adapter can be swapped in behind the same port (D-23/D-24).
**Source:** 02-02-SUMMARY.md

### OTel API in core, Logfire only at the composition root (provider-independent observability)
`core/observability.py` imports only the OpenTelemetry **API**; `obs/logfire_backend.py` is the sole `logfire` import site, calling `logfire.configure(send_to_logfire=False)` once at the CLI composition root.
**Rationale:** Observability must survive an SDK swap and not leak into core; keeping the SDK/backend at the edge means core stays vendor-neutral and `send_to_logfire=False` guarantees no egress (OBS-01/02, D-20/D-21).
**Source:** 02-02-SUMMARY.md

### run_id minted from the OTel trace id and stamped into provenance
Each draft opens a `dogen.draft` span and derives `run_id = format(span.get_span_context().trace_id, "032x")`, stamping it onto the `generations[]` entry written to provenance.
**Rationale:** The on-disk audit surface and the runtime trace must line up (OBS-03 correlation); deriving the id from the trace id is the cheapest way to make them identical and survives the SDK propagating W3C trace context.
**Source:** 02-02-SUMMARY.md

### import-linter as the declarative seam gate, AST check retained belt-and-braces (D-29 keep-both)
A `[tool.importlinter]` forbidden contract bans `copilot`, `github_copilot_sdk`, `logfire`, `opentelemetry.sdk`, and `dogen.adapters` from `dogen.core`; the Phase-1 AST `scripts/seam_check.py` and its CI/pre-commit/test wirings are kept unchanged alongside it.
**Rationale:** import-linter is the primary declarative gate but its static graph can miss dynamic forms (e.g. `importlib.import_module` by string constant) that the AST check catches; both are cheap to run together (RESEARCH Pitfall 4).
**Source:** 02-01-SUMMARY.md

### HITL gate as a domain invariant: "no recorded steering → no draft"
The orchestrator refuses to draft (`SteeringRequiredError`, no side effects) unless a prior `steer` event exists in `provenance.steering`; a wholly missing `provenance.yaml` is surfaced as the same refusal, not a file error. The gate lives in core, the CLI only reports it.
**Rationale:** HITL must be provable, not ceremonial (Pitfall 3 "HITL theatre"); making it a consequential domain invariant with no side effects on refusal is what AC5 audits depend on (HITL-01/D-40).
**Source:** 02-02-SUMMARY.md

### Stop-at-reviewed lifecycle: never set committed (SKEL-03)
Progress auto-advances `pending→sourced→drafted` on draft and `→reviewed` on review; no code path ever writes `ProgressState.committed`, enforced by an AST-scan test.
**Rationale:** The framework's hard scope border is singular traceable local commits owned by the human reviewer/merger; the tool must stop before committing (Pitfall 9, SKEL-03).
**Source:** 02-02-SUMMARY.md

### CC-BY-SA-4.0 for drafted docs content vs GPL-3.0-only for code/audit artifacts (D-44)
Drafted `docs/*.md` content is licensed CC-BY-SA-4.0 via `.license` sidecars (no inline SPDX in prose); the `licensing.md` §1/§2/§3.5 CC-BY-SA vs CC-BY-NC-SA self-contradiction was reconciled to CC-BY-SA-4.0; `docs/seam.md` was relicensed from inline GPL to a CC-BY-SA-4.0 sidecar as published content; the committed `.dogen/**` audit surface stays GPL-3.0-only via a `REUSE.toml` aggregate glob.
**Rationale:** Published prose follows the Canonical non-software default (CC-BY-SA), while tool-generated artifacts follow the code license; sidecars keep published pages free of SPDX pollution and keep `reuse lint` green.
**Source:** 02-04-SUMMARY.md

---

## Lessons

### Re-drafting a reviewed unit needs `reviewed` in the progress order ladder
The original `_advance_progress` only ranked `pending→sourced→drafted`, so re-drafting a unit already at `reviewed` mis-walked the ladder. The fix added `reviewed` to `_PROGRESS_ORDER` (index 3) and a `current > drafted_rank` branch that resets cleanly to `drafted` with one transition and no backward `sourced` re-stamp.

**Context:** Surfaced as a WR-04 verification follow-up; the lifecycle ladder must enumerate every reachable post-draft state to keep transitions monotonic and idempotent (commit 78c154f, raised verification from 18/19 to 19/19).
**Source:** 02-VERIFICATION.md

### review-before-draft deserves a specific UX message, not a generic read error
`dogen review` run before any draft originally surfaced a generic file-read error; the fix added a separate `FileNotFoundError` handler on `read_progress` emitting "has not been drafted yet — run `dogen draft <id>` first" at exit 2.

**Context:** WR-05 UX gap closed during re-verification — "good UX is a primary requirement," so error paths need command-specific guidance (commit 668f4f8).
**Source:** 02-VERIFICATION.md

### Don't fabricate context_origins / tools_used — record honest empties
`_record_generation` was copying `unit.sources` into `Generation.context_origins` and hardcoding `tools_used=[]`, fabricating audit evidence on the real Copilot path and violating D-37. The fix added `context_origins`/`tools_used` to `DraftResult` so a provider can report what it actually read/used, defaulting to honest empty lists until it can.

**Context:** BL-01, the single blocker — surfaced by the Codex cross-model review and missed by the Claude review; an audit surface that claims requested sources were read undermines the project's core AC5 value (commit f3a1dba).
**Source:** 02-REVIEW-codex.md

### A lazy import inside an `except` clause silently breaks the seam
The CLI `draft` command caught `except _backend_unavailable_error()`, a helper that imported `dogen.adapters.copilot` to obtain the class — and Python evaluates that expression during matching, pulling the SDK adapter onto the `--provider mock` path for any non-steering error. The fix catches `RuntimeError` and classifies by `type(exc).__name__ == "BackendUnavailableError"`.

**Context:** WR-01 — the deferred-import seam guarantee (D-25) is defeated if catching an error depends on a lazy import; the existing no-import test only covered the happy path so the regression was invisible (commit 4197a54).
**Source:** 02-REVIEW.md

### Errors raised during request construction escape the command's try-block
`select_provider(provider)` raises `ValueError` on an unknown name, but it was called during `DraftRequest` construction *before* the `try:`, so `dogen draft --provider banana` exited with an unhandled traceback instead of a clean exit-2 message. The fix moved the whole `DraftRequest` construction inside the `try:`.

**Context:** WR-06 — anything that can raise belongs inside the handler that is supposed to render its message; a typo should not produce a stack trace (commit ee86206).
**Source:** 02-REVIEW-codex.md

### A schema field documented as a "mirror" must actually be maintained or marked reserved
`Unit.status` was documented as a mirror of progress lifecycle state but was never written back, so every `unit.md` permanently read `status: pending` while `progress.yaml` advanced — visible in the committed dogfood unit. The fix re-documented it as "reserved; not yet maintained" with `progress.yaml` as the sole source of truth.

**Context:** WR-02 — for a provable/auditable surface, a field that silently disagrees with real state is an audit-integrity hazard, not cosmetic (commit 730dd54).
**Source:** 02-REVIEW.md

### SDK reasoning effort and recorded provenance effort can silently disagree
The Copilot provider used its own `effort` for the SDK `reasoning_effort` while the orchestrator recorded `request.effort` (defaulting to `medium`) — two independent values that could diverge once parameterised. The fix added `effort_used: Effort | None` to `DraftResult`; the provider reports the effort it actually ran at, and the orchestrator records `result.effort_used or request.effort`.

**Context:** IN-03 — the value the provider actually ran at must be the single source of truth for the audit record, not a separately-defaulted request field (commit d343155).
**Source:** 02-REVIEW-FIX.md

### Write the audit record before the observable draft, and write YAML atomically
`_run_draft` performed `write_draft → write_provenance → _advance_progress` with no transaction, so a crash could leave a drafted `.md` with no provenance — the exact gap AC5 forbids. The fix reordered to `_record_generation → write_provenance → _advance_progress → write_draft` (draft last) and routed YAML/draft writes through an `_atomic_write_text` (temp + fsync + `os.replace`).

**Context:** WR-03 — durability ordering matters for a provenance-first framework; a crash may now only leave a re-runnable audit row with no draft, never a draft with no audit (commit e37a828).
**Source:** 02-REVIEW-FIX.md

### `git config` reads should use the explicit `--get` form
The git-identity adapter shelled `["git", "config", "user.name"]`, the deprecated read form that returns the last value and behaves oddly for multi-valued keys. The fix switched to `["git", "config", "--get", "user.name"]`/`--get user.email`.

**Context:** IN-02 — for a field that becomes the immutable author of an audit record, the explicit, predictable read form matters (commit 5ff604b).
**Source:** 02-REVIEW.md

---

## Patterns

### Anti-corruption mapping at the seam (SDK event → DraftResult)
`adapters/copilot/mapping.py::to_draft_result(evt, run_id)` reads `content`/`model`/`output_tokens` defensively via `getattr` (the payload is a union over ~90 SDK event types) and coerces missing model/tokens to `unknown`/`0`, so neither the SDK union nor any `None` ever reaches the domain `DraftResult`.

**When to use:** Whenever a vendor SDK returns wide union types that must cross into a typed domain model — translate at the adapter boundary so vendor shapes never leak into core.
**Source:** 02-03-SUMMARY.md

### Lazy provider-factory dict so the mock path never imports the SDK adapter
`select_provider` is a dict dispatch of factories (not an if/elif ladder); the `copilot` branch is a lazily-imported factory (`# noqa: PLC0415` load-bearing) so resolving `mock` never loads `adapters/copilot/` or the SDK.

**When to use:** When one dispatch branch carries an expensive or seam-sensitive import that the other branches (and CI) must never trigger; combine with a no-import regression test on the cheap path.
**Source:** 02-02-SUMMARY.md

### In-memory OTel SDK exporter for test-only correlation assertions
Core stays OTel-API-only (a no-op tracer by default), so tests install a test-only `TracerProvider + SimpleSpanProcessor + InMemorySpanExporter` in a fixture (resetting OTel's `_TRACER_PROVIDER_SET_ONCE` guard for order-independence) and assert `provenance.generations[0].run_id == format(finished_span.context.trace_id, "032x")`.

**When to use:** To prove run-level correlation between emitted spans and an on-disk record without putting the OTel SDK into production core code.
**Source:** 02-02-SUMMARY.md

### AST-scan test asserting `committed` is never written
`test_orchestrator_never_writes_committed` AST-walks the orchestrator source and fails if `ProgressState.committed` is ever referenced as an attribute access (docstrings/comments allowed).

**When to use:** To enforce a "this state/operation is never reachable" scope invariant structurally, so adding the forbidden transition later trips a test rather than slipping through.
**Source:** 02-02-SUMMARY.md

### Backend-unavailable wrapping by exception type at the adapter
The Copilot provider wraps `StopError`, connection/OS/timeout failures, status-check failures, and a missing assistant message into a single handled `BackendUnavailableError` (defined in the adapter, not core); the CLI classifies it by name so the mock path never imports the adapter.

**When to use:** When an external backend has many distinct failure modes that should all degrade to one clear, non-crashing operator message and a nonzero exit.
**Source:** 02-03-SUMMARY.md

### Live-SDK path gated behind an explicit opt-in flag/env
`scripts/smoke_draft.py` gates its real-SDK run behind `--live` / `DOGEN_SMOKE_LIVE=1`; the default run makes no SDK call and prints how to opt in, so the harness's argument-handling and backend-unavailable branches are unit-testable in CI with zero network.

**When to use:** For a manual/operator-only integration harness that still needs its control-flow covered by automated tests without ever calling the real service.
**Source:** 02-03-SUMMARY.md

### Atomic write-to-temp-then-rename for audit files
`FilesystemPlanningStore._atomic_write_text` writes to a temp file with `flush`/`fsync`, then `os.replace`, and both `_write_yaml` and `write_draft` route through it.

**When to use:** Whenever a partial/torn write of an on-disk record would corrupt an audit or state file; pair with side-effect ordering (durable record before observable artifact).
**Source:** 02-REVIEW-FIX.md

### Single-sourced seam gate across four surfaces
The seam invariant is single-sourced four ways: the `pyproject.toml` import-linter contract ↔ a CI step ↔ a pre-commit hook ↔ a pytest subprocess test, mirroring the Phase-1 `seam_check` pattern.

**When to use:** For any invariant that must hold in CI, locally, and in the editor — wire one declaration into all enforcement surfaces and add a test that runs the gate so a removed wiring is caught.
**Source:** 02-01-SUMMARY.md

---

## Surprises

### import-linter cannot forbid an external subpackage unless its top-level is a graphed root
Forbidding `opentelemetry.sdk` from core required adding `include_external_packages = true` and naming `opentelemetry` as a second `root_packages` entry; otherwise `lint-imports` errored that the subpackage could not be forbidden.

**Impact:** A blocking config adjustment in plan 01; the workaround does not relax the seam — core may still use the OTel *API*, only the `.sdk` subpackage is forbidden.
**Source:** 02-01-SUMMARY.md

### A relative `working_directory` crashes create_session with JSON-RPC -32603
`client.create_session(...)` rejects a relative `working_directory` (including `"."`) with "Directory path must be absolute"; the provider and smoke harness always pass an absolute repo-root path.

**Impact:** Surfaced during the live probe in plan 03; both the adapter and the harness had to resolve `os.path.abspath(... or os.getcwd())`, and `create_session` is itself a coroutine whose result is an async context manager (`async with await client.create_session(...)`).
**Source:** 02-03-SUMMARY.md

### The real file-edit tool is named `edit`, not the assumed `str_replace_editor`
The blocking A1 checkpoint live-probe confirmed the read-only allowlist as exactly `grep`/`glob`/`view` and revealed the registered write tool is `edit`; the plan-assumed `str_replace_editor` is not a registered name on this runtime, and `SystemMessageAppendConfig`'s real key is `content` (not the assumed `append`).

**Impact:** The denylist and system-message config were locked to verified strings rather than assumptions; the recorded CLI runtime version `1.0.64-0` became the SKEL-05 bump-gate pin.
**Source:** 02-03-SUMMARY.md

### Stale dogfood provenance shipped a pre-fix `model_version` artifact
The committed `.dogen/units/cli-reference/provenance.yaml` carried `model_version: mock-model` (the pre-fix value) because it was written before the mock provider was corrected to `_MOCK_MODEL_VERSION = "mock-1"` and never regenerated — so the repo briefly shipped an AC5 evidence record demonstrating the very bug that had been fixed.

**Impact:** Caught as IN-01 in review; the committed audit file had to be regenerated/corrected to `mock-1` (commit 90fbf48) so the shipped evidence matches current behavior.
**Source:** 02-REVIEW.md

### `reuse lint` false-positives spread from one planning file to four
`reuse lint` flags `.planning/` SUMMARY/VERIFICATION prose that *quotes* an SPDX token in narrative text; the count grew across plans (1 → 2 → 4 files) as each new SUMMARY described the prior false positive, and authors had to phrase their own SUMMARYs to avoid adding a fifth trigger.

**Impact:** A persistent whole-repo lint noise (DEF-02-01/02) deferred to a `REUSE-IgnoreStart/End` housekeeping pass; every distributable source/docs file passes individually, so it does not affect shippable artifacts.
**Source:** 02-04-SUMMARY.md

### `ty` does not honour an inline `type: ignore` for a test double
`uv run ty check` reports a diagnostic at `tests/test_orchestrator_hitl.py:346` where a `_FailingDraftStore` test double is not assignable to `PlanningStore`, and the inline `# type: ignore[arg-type]` is not honoured by `ty`.

**Impact:** A non-blocking, pre-existing type-checker quirk flagged for follow-up during validation; the full pytest suite, ruff, lint-imports, and the Sphinx `-W` build are all green regardless.
**Source:** 02-VALIDATION.md
