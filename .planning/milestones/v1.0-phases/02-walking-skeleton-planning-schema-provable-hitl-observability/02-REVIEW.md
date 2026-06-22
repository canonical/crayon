---
phase: 02-walking-skeleton-planning-schema-provable-hitl-observability
reviewed: 2026-06-20T00:00:00Z
depth: deep
files_reviewed: 36
files_reviewed_list:
  - .dogen/units/cli-reference/progress.yaml
  - .dogen/units/cli-reference/provenance.yaml
  - .dogen/units/cli-reference/unit.md
  - .github/workflows/ci.yml
  - LICENSES/CC-BY-SA-4.0.txt
  - docs/cli-reference.md
  - docs/cli-reference.md.license
  - docs/conf.py
  - docs/index.md
  - docs/index.md.license
  - docs/seam.md
  - docs/seam.md.license
  - scripts/smoke_draft.py
  - src/dogen/adapters/copilot/__init__.py
  - src/dogen/adapters/copilot/mapping.py
  - src/dogen/adapters/copilot/provider.py
  - src/dogen/adapters/copilot/tools.py
  - src/dogen/adapters/git_identity.py
  - src/dogen/adapters/mock_provider.py
  - src/dogen/adapters/planning_fs.py
  - src/dogen/cli/main.py
  - src/dogen/core/models.py
  - src/dogen/core/observability.py
  - src/dogen/core/orchestrator.py
  - src/dogen/core/ports.py
  - src/dogen/obs/__init__.py
  - src/dogen/obs/logfire_backend.py
  - tests/test_cli_unit_new.py
  - tests/test_copilot_backend_unavailable.py
  - tests/test_copilot_mapping.py
  - tests/test_docs_build.py
  - tests/test_loop_mock_e2e.py
  - tests/test_models.py
  - tests/test_observability_correlation.py
  - tests/test_orchestrator_hitl.py
  - tests/test_planning_fs.py
  - tests/test_seam_importlinter.py
  - tests/test_smoke_harness.py
findings:
  critical: 1
  warning: 6
  info: 4
  total: 11
status: issues_found
consolidated_with: 02-REVIEW-codex.md  # BL-01 and WR-06 added from the Codex cross-model run
---

# Phase 02: Code Review Report

**Reviewed:** 2026-06-20T00:00:00Z
**Depth:** deep
**Files Reviewed:** 36
**Status:** issues_found

## Summary

This is a clean, well-factored walking skeleton. The seam discipline is genuine and
CI-enforced (core/ carries zero vendor imports, `adapters/copilot/` is the sole SDK
site, the mock is a real second provider), path-traversal controls are layered and
positive-containment based, git identity is read through a fixed allowlist with no
interpolation, and all deserialization uses `yaml.safe_load`. No injection, hardcoded
secrets, eval/exec, or unsafe-deserialization defects were found, and no BLOCKER-class
issue surfaced.

The adversarial pass did find one genuine seam-leak bug, one documented schema
invariant that is never enforced, and several robustness/consistency gaps that should
be fixed before this skeleton is built upon. The most important is WR-01: the CLI
`draft` command imports the Copilot SDK adapter on the *mock* error path, directly
violating the D-25 guarantee the code is explicitly written to uphold.

## Narrative Findings (AI reviewer)

### Blockers

#### BL-01: `Generation.context_origins` / `tools_used` are fabricated, violating D-37 (cross-model: Codex)

**File:** `src/dogen/core/orchestrator.py:266-279`
**Source:** Surfaced by the Codex cross-model review (`02-REVIEW-codex.md`); verified against code by the orchestrator.
**Issue:** `_record_generation` sets `context_origins=[s.path or s.ref or "" for s in unit.sources]` and `tools_used=[]`. This copies the unit's *human-pointed* `sources` into the field documented as the *agent-read* context — exactly the collapse decision **D-37** forbids ("Unit.sources (human-pointed) vs Generation.context_origins (agent-read) never collapse"). `tools_used` is hardcoded empty even on the real Copilot path, where the bounded grep/glob/view ToolSet is actually exercised. The mock path is harmless (it reads nothing), but the real provider path writes a provenance record that claims the requested sources were the read context and that no tools ran — fabricated audit evidence that directly undermines the AC5 provenance guarantee, the project's core value.
**Fix:** Stop fabricating. Until a provider can report what it actually read/used, record `context_origins=[]` and `tools_used=[]` (an honest "nothing observed") rather than copying `unit.sources`. Add `context_origins`/`tools_used` to `DraftResult` so `CopilotDraftingProvider` can populate them from the SDK events (mock returns empty), and have `_record_generation` read them from `result`, not from `unit.sources`. This restores D-37 and makes the audit record truthful.

### Warnings

#### WR-01: `draft` CLI imports the Copilot SDK adapter on the mock error path (seam leak)

**File:** `src/dogen/cli/main.py:182-190`
**Issue:** Python evaluates `except` clauses in order, and `except
_backend_unavailable_error() as exc:` *calls* `_backend_unavailable_error()` to obtain
the class whenever no earlier clause has matched. That helper runs `from
dogen.adapters.copilot import BackendUnavailableError`, which imports the Copilot SDK
adapter (and `copilot` itself). On the `--provider mock` path, any exception that is
not `SteeringRequiredError` — a `ValueError` from a malformed `unit.md`, a mismatched
`unit_id`, or any unexpected error raised inside the mock provider — forces evaluation
of this `except` expression and pulls `adapters/copilot/` onto the mock path. This
defeats the exact D-25 invariant the deferred import was written to protect ("the mock
path never imports `adapters/copilot/`"), and on a host without the SDK installed it
converts a clean domain error into an `ImportError` crash. `test_select_provider_mock_does_not_import_copilot_adapter` only covers the no-error
path, so this regression is invisible to the suite.
**Fix:** Never make catching the error depend on a lazy import. Either give
`BackendUnavailableError` a base class defined in `core/` and catch the base, or
classify by name without importing:
```python
try:
    draft_path = asyncio.run(draft_use_case(request))
except SteeringRequiredError as exc:
    typer.echo(f"Refusing to draft: {exc}", err=True)
    raise typer.Exit(code=1) from exc
except (FileNotFoundError, ValueError) as exc:
    typer.echo(f"Cannot draft {unit_id!r}: {exc}", err=True)
    raise typer.Exit(code=2) from exc
except RuntimeError as exc:  # BackendUnavailableError is a RuntimeError
    if type(exc).__name__ == "BackendUnavailableError":
        typer.echo(f"Copilot backend unavailable: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    raise
```

#### WR-02: `Unit.status` is documented as a progress mirror but is never updated

**File:** `src/dogen/core/models.py:145-157`; `src/dogen/core/orchestrator.py:282-324`; `src/dogen/cli/main.py:149-269`
**Issue:** `Unit.status` is documented as "Mirror of the unit's progress lifecycle
state," but neither the orchestrator nor the CLI ever writes it back to `unit.md`.
After `steer → draft → review`, on-disk `unit.md` still reads `status: pending` while
`progress.yaml` reads `reviewed`. The committed dogfood unit proves it:
`.dogen/units/cli-reference/unit.md` has `status: pending` while
`.dogen/units/cli-reference/progress.yaml` is `reviewed`. The field is therefore a
permanent falsehood in every unit. Because the project's value proposition is a
*provable, auditable* surface (AC5), a field that silently disagrees with the real
state is an audit-integrity hazard, not merely cosmetic.
**Fix:** Either (a) drop `status` from `Unit` and make `progress.yaml` the sole source
of truth (lower-risk, since `unit.md` is hand-edited with no YAML round-trip), or (b)
rewrite `unit.md` front-matter `status` on each transition. If the field is reserved
for a later phase, change the docstring to say "reserved; not yet maintained" so the
schema stops advertising a guarantee it does not keep.

#### WR-03: Drafting writes draft + provenance + progress with no partial-failure handling

**File:** `src/dogen/core/orchestrator.py:222-240`
**Issue:** `_run_draft` performs three independent side effects in sequence —
`write_draft`, then `write_provenance`, then `_advance_progress` (itself a
read-then-write of `progress.yaml`) — with no transaction and no compensation. If
`write_provenance` raises (disk full, permission change, interrupt), the draft `.md`
is already on disk under `docs/` but no `generations[]` entry records it: a drafted
output with no provenance, the exact gap the AC5 audit guarantee is meant to forbid.
A failure in `_advance_progress` leaves provenance updated but progress stale. For a
framework whose selling point is a trustworthy provenance trail, an output that can
exist with no recorded generation is a real correctness concern.
**Fix:** Make the audit record durable before the draft is observable — write
provenance (and progress) first, then write the draft file last — so a crash can never
leave a draft with no audit row. Use write-to-temp-then-rename for each YAML to avoid
torn writes.

#### WR-04: `steer` can silently overwrite a prior steering event and invert the audit ordering

**File:** `src/dogen/cli/main.py:115-146`
**Issue:** `steer` unconditionally overwrites `provenance.steering` with a fresh
`Steering(...)` built from the *current* `unit.md` intent/audience. Re-running `steer`
after a unit has been drafted (or reviewed) silently replaces the recorded steering act
with a new timestamp — and possibly new intent/audience — while existing
`generations[]` entries still reference the old steering. The "steering provably
precedes the draft" invariant (HITL-02/AC5) relies on `steering.at <
generations[0].at`; a re-steer after drafting produces `steering.at >
generations[0].at`, inverting the ordering the audit depends on, with no warning and no
test coverage.
**Fix:** Refuse to overwrite an existing steering event unless an explicit
`--force`/`--re-steer` flag is passed (mirroring the `unit new` clobber guard), or make
steering additive (append events to a list) so the trail is never rewritten. At
minimum, warn when overwriting steering on a unit that already has generations.

#### WR-05: `mapping.to_draft_result` lets a `None` content crash instead of degrading

**File:** `src/dogen/adapters/copilot/mapping.py:64-75`
**Issue:** `text = getattr(data, "content", "")` defaults a *missing* attribute to
`""`, but if the SDK delivers `content=None` (the module docstring notes fields can
arrive unfinalised), `None` flows into `DraftResult.text`, typed `str`. Pydantic v2
raises a `ValidationError` on `None` for a `str` field, surfacing as an uncaught crash
inside `_require_assistant_message` rather than the handled `BackendUnavailableError`
the adapter promises for every backend oddity (SKEL-05/D-27). `model` and
`output_tokens` are guarded with `or` fallbacks; `content` — the field most likely to
arrive empty on a truncated stream — is the one that is not.
**Fix:** Coerce defensively to match the other fields: `text = getattr(data,
"content", None) or ""`, and/or validate non-null content before mapping, raising
`BackendUnavailableError` otherwise.

#### WR-06: Unknown `--provider` raises `ValueError` outside the `draft` try-block (unhandled traceback) (cross-model: Codex)

**File:** `src/dogen/cli/main.py:170-190`; `src/dogen/adapters/mock_provider.py:160-185`
**Source:** Surfaced by the Codex cross-model review (`02-REVIEW-codex.md`); verified against code by the orchestrator.
**Issue:** `select_provider(provider)` raises `ValueError` on an unknown provider name, but it is called at `main.py:175` during `DraftRequest` construction — *before* the `try:` at line 180. The command's own `except (FileNotFoundError, ValueError)` handler (line 188) therefore never catches it, so `dogen draft UNIT --provider banana` exits with an unhandled `ValueError` traceback instead of the intended clean exit-2 message. "Good UX is a primary requirement" (PROJECT.md), so an uncaught stack trace on a simple typo is a real defect.
**Fix:** Move `select_provider(provider)` (and ideally the whole `DraftRequest` construction) inside the `try:` block so the existing `except (FileNotFoundError, ValueError)` path renders the clean "Cannot draft … unknown provider 'banana'; choose one of: copilot, mock" message with exit code 2.

### Info

#### IN-01: Committed dogfood provenance records a stale `model_version`

**File:** `.dogen/units/cli-reference/provenance.yaml:10`
**Issue:** The committed generation has `model_version: mock-model`, duplicating the
model name — the exact bug the WR-03 fix (commit `7238661`) corrected in the mock
provider (`_MOCK_MODEL_VERSION = "mock-1"`). The provenance file was written by an
earlier commit (`2858671`) before the fix and never regenerated, so the repo ships a
dogfood "AC5 evidence" record that demonstrates the pre-fix bug. Not a code defect, but
the committed audit surface contradicts current shipped behaviour.
**Fix:** Regenerate the dogfood unit's provenance with the current mock provider so the
committed audit record reads `model_version: mock-1`.

#### IN-02: `git config` reads omit `--get`, risking surprising values

**File:** `src/dogen/adapters/git_identity.py:31-34`
**Issue:** `["git", "config", "user.name"]` is the deprecated read form; without
`--get` it returns the last value and behaves differently for multi-valued keys. For a
field that becomes the immutable author of an audit record, the explicit read form is
more predictable.
**Fix:** Use `["git", "config", "--get", "user.name"]` and `--get user.email`.

#### IN-03: SDK reasoning effort and recorded provenance effort are two independent values

**File:** `src/dogen/adapters/copilot/provider.py:62-101`; `src/dogen/core/orchestrator.py:266-278`
**Issue:** `CopilotDraftingProvider.__init__` takes `effort` and uses it for the SDK
`reasoning_effort`, but the orchestrator records `request.effort` (defaulting to
`Effort.medium` on `DraftRequest`) in the `Generation`, and the CLI never sets either.
The effort the SDK actually runs at (`provider._effort`) and the effort written to the
audit record (`request.effort`) can disagree. Both default to `medium` today, so it is
latent, but the provenance record can misrepresent the effort actually used once either
is parameterised.
**Fix:** Have the provider report the effort it used in `DraftResult`, or plumb one
effort value from the CLI through `DraftRequest` into the provider so a single source of
truth feeds both the SDK call and the provenance entry.

#### IN-04: Un-flagged `draft` defaults to `copilot`, amplifying WR-01

**File:** `src/dogen/cli/main.py:152-155`; `src/dogen/adapters/mock_provider.py:160`
**Issue:** `dogen draft UNIT_ID` with no `--provider` defaults to `copilot` (the
documented production default), so the most common invocation eagerly resolves the real
SDK adapter. Intentional, but it widens WR-01's blast radius: the common command is the
one that triggers the SDK import. No independent fix required beyond WR-01.

---

_Reviewed: 2026-06-20T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
