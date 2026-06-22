# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — MVP

**Shipped:** 2026-06-20
**Phases:** 2 | **Plans:** 8 | **Sessions:** ~5 (git-clustered across 2 days; not separately tracked)

### What Was Built
- **Phase 1 — Compliant Scaffold & Provider-Seam Boundary:** a REUSE-compliant `src/dogen/` package from commit 1 (per-file SPDX via a committed Jinja2 notice template, GPL-3.0-only), a hexagonal layout confining all vendor imports to `adapters/copilot/`, an AST seam guardrail single-sourced across pytest/CI/pre-commit, and a SHA-pinned least-privilege CI gate suite.
- **Phase 2 — Walking Skeleton, Planning Schema, Provable HITL & Observability:** the F1 planning-directory schema v0 (Pydantic v2, `schema_version: 0`, reserved verification fields, `sources` vs `context_origins` kept distinct), the async `core/orchestrator.py` drafting use-case enforcing "no recorded steering → no draft", a deterministic SDK-free `MockDraftingProvider` plus the real `CopilotDraftingProvider` on the pinned `github-copilot-sdk==1.0.2` behind one `DraftingProvider` port, OTel-API observability with `run_id`↔provenance correlation, and the `dogen unit new / steer / draft / review` CLI emitting Sphinx-publishable MyST and stopping at `reviewed`.

### What Worked
- **Foundations-first paid off.** Setting the seam boundary, REUSE licensing, and CI enforcement *before any drafting logic* (Phase 1) made the Phase-2 provider swap cheap — the real Copilot adapter slotted in behind the very port the mock had already proven, with no core rewrite. The "pour concrete in stages" philosophy held.
- **Single-sourcing invariants across enforcement surfaces.** The seam check (and later the import-linter contract) was wired once into pytest + CI + pre-commit (+ the editor via config), so the three gates cannot drift. Same pattern reused for both phases.
- **A deterministic, SDK-free mock as the CI proof.** The whole loop runs in CI with no Copilot token or network, keeping the skeleton always demoable and making the swappability claim testable (`isinstance` against the port for both providers).
- **Cross-model review caught the highest-stakes bug.** The single blocker (BL-01: orchestrator fabricating `context_origins`/`tools_used` on the real path) was surfaced by the Codex cross-model review and *missed* by the Claude review — an audit surface that lies about what was read would have undermined the project's core AC5 value.

### What Was Inefficient
- **`reuse lint` on planning prose was a recurring tax.** A whole-repo `reuse lint` gate also lints committed `.planning/` docs; any doc that *quotes* an SPDX token in prose is misread as a real declaration. The false-positive count crept 1 → 2 → 4 as each new SUMMARY described the prior one, and it forced a post-audit quick task (260620-sa1) to wrap the prose and get CI green.
- **Three CI gates were red at audit time** (reuse lint, `ty` test-double, a stray `ruff format`), all non-functional but all latent until the milestone audit ran them against the working tree. A green local "full gate suite" run at phase close — not just the test subset — would have caught them earlier.
- **A stated invariant ("no `REUSE.toml` ever", D-04) had to be reversed mid-phase** once it became clear committed `.planning/` meta is in `reuse lint` scope — costing a re-plan and a security ratification.
- **A point-in-time security disposition ("#1606 eliminated") was carried as if permanent** and had to be explicitly un-carried in Phase 2 once the SDK became a real runtime dependency.

### Patterns Established
- **`.license` sidecars** for files that can't carry an inline header (generated lockfiles, Markdown/docs, the Jinja2 template itself, published content).
- **Meta-only `REUSE.toml` at aggregate precedence** so per-file source headers still win while whole-repo lint goes green; **`REUSE-IgnoreStart/End`** to suppress SPDX-token-in-prose false positives.
- **Anti-corruption mapping at the seam** (SDK event → domain `DraftResult` via defensive `getattr`) so wide vendor union types never reach core.
- **Lazy provider-factory dispatch + a no-import regression test** so the mock path never loads the SDK adapter; **import-linter declarative contract kept belt-and-braces alongside the AST check** (D-29 keep-both).
- **Durability ordering for audit-first writes:** record provenance before the observable draft, write YAML atomically (temp + fsync + `os.replace`).
- **AST-scan tests for "never reachable" invariants** (e.g. `committed` is never written).

### Key Lessons
1. **A whole-repo lint gate lints your planning prose too.** Anything git-tracked is in scope; SPDX tokens quoted in narrative trip `reuse`. Wrap new planning docs proactively or the red count creeps every milestone.
2. **Run the *full* gate suite (not just tests) at phase close.** `ty`, `ruff format --check`, and `reuse lint` reds stayed invisible until the milestone audit because phase verification leaned on the test subset.
3. **Foundations that are expensive to retrofit should go in first** — the seam + licensing + observability sequencing made later work cheap and is worth repeating.
4. **Record requirement IDs in a machine-readable key, not just `tags:`.** SKEL-02's tags-only record made the audit rollup flag it `partial` despite being fully verified — pure bookkeeping cost.
5. **Cross-model / adversarial review earns its keep on audit-integrity bugs.** The one real blocker was only caught by the second model.
6. **A schema field documented as a "mirror" must be maintained or marked reserved** — a silently-stale field (`Unit.status`) is an audit-integrity hazard, not cosmetic.

### Cost Observations
- Model mix: not instrumented this milestone (config `model_profile: quality`, opus-leaning). Add per-session model accounting before v1.1 if cost tracking matters.
- Sessions: ~5 working clusters across 2 calendar days (2026-06-19 → 2026-06-20), 85 commits.
- Notable: the GSD per-plan → verify → validate → security → audit chain added overhead but caught real, shippable-affecting issues (BL-01, the stale dogfood provenance, the CI-red gates) before close.

---

## Milestone: v1.1 — Live Copilot Path Hardening

**Shipped:** 2026-06-22
**Phases:** 2 | **Plans:** 3 | **Sessions:** ~2 (single calendar day; 44 commits)

### What Was Built
- **Phase 3 — Live Copilot path runs out of the box:** a Wave-0 kwargs-capturing fake-SDK harness in `conftest.py` (D-08 private-import + V4 toolset-boundary regression guards), then five adapter fixes TDD'd against it — `gpt-5-mini` default + a `--model` flag threaded through `select_provider`, a `PermissionHandler.approve_all` handler over the read-only `grep`/`glob`/`view` allowlist, family-gated `reasoning_effort`, and a `-32603` model-rejection (`ModelRejectedError`) vs generic-backend (`BackendUnavailableError`) error split across both the draft and status paths.
- **Phase 4 — Honest observed provenance:** a pure `tool_events_to_provenance` seam helper translating observed `TOOL_EXECUTION_START` events into `context_origins` (view-read paths) + `tools_used` (`builtin:<name>`), attached in `_run_draft` via the existing `model_copy(update=...)`, first-seen de-duped and honest-empty on doubt — completing the BL-01 honesty arc.

### What Worked
- **The v1.0 seam investment compounded.** An entire hardening milestone stayed inside the single Copilot adapter (`provider.py`, `mapping.py`) plus the orchestrator/CLI seam — +1,420/−58 across 14 src/test files, zero core rewrite. Decoupling is the gift that keeps giving.
- **Build the test harness first, reuse it everywhere.** The Wave-0 fake-SDK stub (plan 03-01) made all five Phase-3 fixes *and* the Phase-4 provenance work unit-provable with no token/network — `get_events()` was threaded into the same stub for Phase 4.
- **TDD mode held the line.** Every behaviour-adding task had a `test(...)` RED commit before its `feat(...)` GREEN commit, verified in git log — the discipline was visible in history, not just asserted.
- **Honest-empty-by-design.** Defensive `getattr` + `isinstance` guards mean a malformed/None-arg event degrades to empty provenance rather than crashing the draft or fabricating an origin — the audit surface fails safe.
- **Brownfield-finding-driven scope stayed tight.** Four concrete gaps from one real live run → exactly 7 requirements → zero scope creep.

### What Was Inefficient
- **The `reuse lint` planning-prose / temp-dir tax recurred** — exactly as v1.0 predicted. The untracked `temp/.dogen/` live-run artifacts and SUMMARY files quoting SPDX tokens tripped whole-repo `reuse lint` again; every shipped file was individually `lint-file`-clean, but the friction repeated. The v1.0 candidate lesson is now cross-validated.
- **A latent lint red from the prior plan blocked the next.** Two `E501` docstring lines in the 03-01 harness blocked the 03-02 `ruff check` gate and had to be wrapped mid-plan — a small instance of the v1.0 "run the full gate suite at phase close" lesson, also now cross-validated.
- **CONTEXT.md pointed at the wrong SDK event carrier** (`ToolInvocation`); RESEARCH corrected it to `TOOL_EXECUTION_START`/`ToolExecutionStartData`. Caught before code, but the initial context capture was wrong.
- **The live gate is operator attestation, not captured observation.** D-24 "approved" closes the manual gate, but the per-criterion command outputs / the real `provenance.yaml` were not recorded in-framework (no token/network here) — the audit trail rests on the operator's word plus the green fake-SDK suite.

### Patterns Established
- **Family-gate optional SDK params** by computing value-or-`None` and passing unconditionally (the SDK omits falsy from the wire) — avoids an `if/elif` kwargs ladder.
- **Disambiguate an overloaded JSON-RPC code** by requiring BOTH the code AND a message signature, falling through to the generic handler otherwise.
- **Classify domain errors at the CLI by `type(exc).__name__`** so the `--provider mock` path never imports the adapter or SDK (preserves the seam).
- **Observe-then-translate:** read full session history with `get_events()` *inside* the open session block, translate in a pure `mapping.py` helper — the provider stays a thin orchestration site and the translation is independently unit-testable.
- **Shared fake-SDK harness with honest-empty defaults** (`_StubSession` events default to `[]`) reused across phases, keeping happy-path tests green while new behaviour is scripted in.

### Key Lessons
1. **The seam pays compound interest.** A whole hardening milestone touching ~14 files and never leaving one adapter is the dividend of the v1.0 decoupling discipline — keep paying it forward.
2. **Whole-repo `reuse lint` tax is now a confirmed recurring cost** (cross-validated v1.0 → v1.1). Worth a durable fix: a scoped `reuse` dir-ignore for `temp/` live-run artifacts and an established prose-wrap habit for SUMMARYs, rather than re-paying per milestone.
3. **Capture live-verification evidence in-framework.** A manual-only gate (D-24) is only as auditable as what it records; a pasted `provenance.yaml` / command output would turn operator attestation into observed evidence.
4. **Trust RESEARCH over stale CONTEXT for vendor SDK shapes** — the event-carrier correction was a research-stage catch that would have been an expensive runtime surprise.
5. **Brownfield-finding-driven scoping keeps a milestone honest** — real gaps from a real run map cleanly to requirements and resist scope creep.

### Cost Observations
- Model mix: still not instrumented (config `model_profile: quality`, opus-leaning). The v1.0 action item (per-session model accounting) was not picked up — carry it forward if cost tracking matters.
- Sessions: 1 calendar day (2026-06-22), 44 commits.
- Notable: fast — 2 phases / 3 plans / ~7 tasks shipped in a day, helped by the tight brownfield scope and the reused Wave-0 harness. The full GSD chain (verify → security → UAT) ran without surfacing a shippable-affecting blocker this time.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | ~5 | 2 | Foundations-first sequencing; single-sourced invariants across CI/pre-commit/pytest; cross-model review adopted |
| v1.1 | ~2 | 2 | Brownfield-finding-driven scope (real run → 7 reqs); build-harness-first then TDD; whole milestone stayed inside the v1.0 seam |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|--------------------|
| v1.0 | 97 passing | not measured | AST seam guardrail (pure stdlib); deterministic SDK-free mock |
| v1.1 | 131 passing | not measured | Wave-0 kwargs-capturing fake-SDK harness; pure `tool_events_to_provenance` translation helper |

### Top Lessons (Verified Across Milestones)

1. **Whole-repo lint gates lint your planning prose and scratch dirs too** — confirmed v1.0 → v1.1. Wrap SPDX tokens in SUMMARYs and scope-ignore `temp/` live-run artifacts proactively, or re-pay the tax every milestone.
2. **Run the *full* gate suite at phase close, not just tests** — confirmed v1.0 → v1.1 (a prior plan's `E501` blocked the next plan's gate). `ty` / `ruff format` / `reuse lint` reds stay invisible if phase verification leans on the test subset.
3. **Foundations that are expensive to retrofit pay compound interest** — the v1.0 seam + licensing + observability let the entire v1.1 hardening milestone stay inside one adapter. (Strong after two milestones.)
4. *(candidate, needs a third milestone)* — capture live/manual-verification evidence in-framework rather than as operator attestation.
