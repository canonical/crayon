---
phase: 02-walking-skeleton-planning-schema-provable-hitl-observability
reviewed: 2026-06-20T00:00:00Z
depth: standard
files_reviewed: 32
files_reviewed_list:
  - src/dogen/core/models.py
  - src/dogen/core/ports.py
  - src/dogen/core/orchestrator.py
  - src/dogen/core/observability.py
  - src/dogen/adapters/planning_fs.py
  - src/dogen/adapters/git_identity.py
  - src/dogen/adapters/mock_provider.py
  - src/dogen/adapters/copilot/__init__.py
  - src/dogen/adapters/copilot/provider.py
  - src/dogen/adapters/copilot/tools.py
  - src/dogen/adapters/copilot/mapping.py
  - src/dogen/obs/__init__.py
  - src/dogen/obs/logfire_backend.py
  - src/dogen/cli/main.py
  - scripts/smoke_draft.py
  - docs/conf.py
  - docs/cli-reference.md
  - docs/index.md
  - docs/seam.md
  - pyproject.toml
  - .github/workflows/ci.yml
  - .pre-commit-config.yaml
  - .readthedocs.yaml
  - REUSE.toml
  - .gitignore
  - tests/test_models.py
  - tests/test_planning_fs.py
  - tests/test_cli_unit_new.py
  - tests/test_seam_importlinter.py
  - tests/test_orchestrator_hitl.py
  - tests/test_loop_mock_e2e.py
  - tests/test_observability_correlation.py
  - tests/test_copilot_mapping.py
  - tests/test_copilot_backend_unavailable.py
  - tests/test_smoke_harness.py
  - tests/test_docs_build.py
findings:
  critical: 1
  warning: 5
  info: 4
  total: 10
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-06-20T00:00:00Z
**Depth:** standard
**Files Reviewed:** 32
**Status:** issues_found

## Summary

This is a well-structured hexagonal slice. The provider seam is genuinely real
(zero vendor imports in `core/`, enforced by import-linter and an AST guardrail,
and proven by the SDK-free mock), the bounded read-only Copilot toolset is
correctly source-qualified, `create_session` is properly awaited as a coroutine,
the anti-corruption mapping keeps SDK shapes out of `DraftResult`, and the
provable-HITL gate is a domain invariant that refuses to draft (with no side
effects) when steering is absent. Test coverage for the stated invariants is
strong.

However, the security boundary that the phase emphasizes — the `.planning/`
write-guard and path-traversal handling in `planning_fs.py` — is **incomplete in
exactly one place that matters**: the draft output path is built from the
operator-authored `sphinx_target` and is validated *only* against `.planning/`,
not against escaping `docs/` or the repo root. A `sphinx_target` containing `..`
writes outside the repo. The `unit_id` is rigorously validated everywhere it is
used as a path segment; `sphinx_target` is not validated at all. That asymmetry
is the one blocker. The remaining findings are robustness and data-quality
warnings plus minor info items.

## Critical Issues

### CR-01: `write_draft` does not contain `sphinx_target` — arbitrary-path write / traversal

**File:** `src/dogen/adapters/planning_fs.py:166-187`
**Issue:**
`write_draft` builds the output path as
`(root / "docs" / unit.sphinx_target).resolve()` and then guards it only with
`_assert_not_under_planning(...)`. `sphinx_target` is an operator-authored
string loaded verbatim from `unit.md` front-matter (`Unit.sphinx_target`,
`models.py:154`) and is **never validated** — unlike `unit_id`, which is run
through `_reject_unsafe_unit_id` everywhere. Because `Path.resolve()` collapses
`..` segments *before* the guard runs, a `sphinx_target` such as
`../../../etc/cron.d/x` (or `../../escape.md`) resolves to a path entirely
outside `docs/` and outside `root`, and the `.planning/`-only guard does not
catch it.

Verified concretely:

```
sphinx_target = '../../../tmp/evil.md'
(root / 'docs' / sphinx_target).resolve()  -> /tmp/evil.md
forbidden = (root / '.planning').resolve()  -> /root/.planning
blocked by planning guard?  -> False   # escapes both docs/ and root
```

This is a write-primitive outside the intended `docs/` sandbox. It can be
triggered by a hand-edited `unit.md`, and — given the agent reads
attacker-influenceable source content — is precisely the class of "injected
instructions steer it outside drafting" threat the toolset denylist is meant to
contain (T-02.1-01 / T-02.3). The scaffolder defaults `sphinx_target` to
`f"{unit_id}.md"` so the happy path is safe, but the field is explicitly
operator-editable and load-bearing, so it must be contained at the write
boundary.

**Fix:** Resolve the target and assert it stays within `root/docs` (and reject
absolute / `..`-bearing `sphinx_target` early), mirroring the `unit_id`
discipline:

```python
def write_draft(self, unit: Unit, text: str, *, root: Path) -> Path:
    docs_root = (root / "docs").resolve()
    target = (docs_root / unit.sphinx_target).resolve()
    # Containment check: target must be docs_root or live beneath it.
    if target != docs_root and docs_root not in target.parents:
        raise ValueError(
            f"sphinx_target escapes docs/: {unit.sphinx_target!r}"
        )
    self._assert_not_under_planning(target, root=root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target
```

Consider also rejecting an absolute or `..`-containing `sphinx_target` at the
`Unit` model layer (a `model_validator`) so the invariant is enforced once at
the schema boundary, consistent with how `SourceRef` validates its own shape.

## Warnings

### WR-01: `_assert_not_under_planning` only blocks `.planning/`, leaving every other write path uncontained

**File:** `src/dogen/adapters/planning_fs.py:295-313`
**Issue:**
The guard's contract is "refuse to write under `.planning/`", but it is the
*only* containment applied to `write_draft` targets. The method name and the
module docstring ("never writes anywhere under `.planning/`") frame `.planning/`
as the sole forbidden zone, which encourages exactly the gap in CR-01: any path
that escapes `root` but is not under `.planning/` passes. The unit-id writers
(`_unit_md_path`, `_read_yaml`, `_write_yaml`) are safe only because
`_reject_unsafe_unit_id` independently constrains the segment — the planning
guard is not what protects them. This guard should be paired with a positive
"must stay under `root`" containment so it is defense-in-depth rather than the
primary (and partial) control.
**Fix:** Add a `_assert_within_root(target, root=root)` helper that asserts
`root.resolve()` is `target` or in `target.parents`, and call it from every
write method (`scaffold_unit`, `write_draft`, `_write_yaml`). Keep the
`.planning/` guard as an additional, narrower check.

### WR-02: `load_unit` ignores the directory `unit_id`, accepting a mismatched front-matter id

**File:** `src/dogen/adapters/planning_fs.py:145-164`
**Issue:**
`load_unit(unit_id, ...)` reads `.dogen/units/<unit_id>/unit.md`, parses the
front-matter, and returns `Unit(**front)` — but never checks that
`front["unit_id"]` equals the directory `unit_id` it was asked to load. If an
operator renames a unit directory (or hand-edits the `unit_id` field), the
returned `Unit.unit_id` silently disagrees with its on-disk location.
Downstream this propagates: the orchestrator records `unit.unit_id` as the span
attribute (`orchestrator.py:210`) and the CLI `steer`/`review` paths write
provenance/progress keyed by the *requested* `unit_id` while the draft is keyed
off the loaded `Unit` — an audit-record inconsistency in a component whose whole
purpose is a trustworthy audit trail (D-36/AC5).
**Fix:** After parsing, assert consistency:

```python
unit = Unit(**front)
if unit.unit_id != unit_id:
    raise ValueError(
        f"unit.md declares unit_id {unit.unit_id!r} but lives under "
        f"{unit_id!r}"
    )
return unit
```

### WR-03: `model_version` is populated with the model *name*, not a version

**File:** `src/dogen/core/orchestrator.py:253-254`
**Issue:**
`_record_generation` builds `Generation(model=result.model,
model_version=result.model, ...)` — both fields receive the same value because
`DraftResult` carries no version field. The provenance schema documents
`model_version` as "the resolved model version" (`models.py:189-191`), so every
recorded generation has a `model_version` that is actually the model name (e.g.
`"gpt-5"` / `"mock-model"`). For an audit/provenance surface that is the
phase's headline deliverable, a field that silently lies about its meaning is a
real defect, even though it does not crash.
**Fix:** Either add a `model_version` field to `DraftResult` (mapped at the
Copilot seam from the SDK's version data and from a fixed mock constant), or, if
no version is available this phase, record an explicit sentinel
(`model_version="unknown"`) rather than duplicating the model name — and update
the docstring to match what is actually stored.

### WR-04: `_advance_progress` re-stamps `drafted` history entry on every re-draft

**File:** `src/dogen/core/orchestrator.py:267-280`
**Issue:**
`_advance_progress` walks `_AUTO_ADVANCE = (sourced, drafted)` and appends a
history entry whenever `progress.state is not state`. On a *second* `draft` of
an already-`drafted` unit, `state` is `drafted`: the `sourced` branch fires
(state goes `drafted → sourced → drafted`) appending both a spurious `sourced`
and a fresh `drafted` entry, and momentarily moves the lifecycle *backward* to
`sourced` mid-loop. Re-drafting is a plausible operator action (iterate on a
page), so the progress history accrues misleading backward transitions.
**Fix:** Only advance forward. Compare against the lifecycle ordinal and append
solely when moving to a strictly later state, e.g. drive off an ordered list and
skip any target at or before the current state:

```python
order = [ProgressState.pending, ProgressState.sourced, ProgressState.drafted]
current = order.index(progress.state) if progress.state in order else -1
for state in _AUTO_ADVANCE:
    if order.index(state) > current:
        progress.state = state
        progress.history.append(ProgressEntry(at=request.now(), state=state))
```

### WR-05: `review` advances to `reviewed` and appends history unconditionally

**File:** `src/dogen/cli/main.py:241-248`
**Issue:**
`review` sets `progress.state = ProgressState.reviewed` and appends a `reviewed`
history entry on every invocation, with no guard that a draft exists or that the
state is currently `drafted`. Running `review` twice appends two `reviewed`
transitions; running it on a unit that was steered-but-never-drafted (its
`progress.yaml` exists only if a draft ran, so this path requires a manual
`progress.yaml`, but the command does not enforce the precondition) still
advances. For a lifecycle whose history is audit evidence, repeated/duplicate
`reviewed` entries dilute the record. Compare with the orchestrator, which is
careful about which transitions it records.
**Fix:** Guard the transition: only append a `reviewed` entry when
`progress.state is not ProgressState.reviewed`, and consider requiring the unit
be `drafted` before it can be reviewed (clear nonzero exit otherwise).

## Info

### IN-01: `mapping.to_draft_result` reads SDK fields via `getattr` with defaults, masking shape drift

**File:** `src/dogen/adapters/copilot/mapping.py:61-64`
**Issue:**
`text = getattr(data, "content", "")` silently yields an empty draft if the SDK
renames `content`; `model`/`output_tokens` similarly default. The provider does
guarantee the event type before calling, but a future SDK field rename would
degrade to a silent empty/`unknown` draft rather than a clear error at the seam.
**Fix:** Access `data.content` directly (let an `AttributeError` surface a real
mapping bug) and reserve the `or default` only for the documented
`str | None` / `int | None` nullability, not for absent attributes.

### IN-02: `BodyTemplate`/`_render_unit_md` hardcodes `sphinx_target = f"{unit_id}.md"` with no namespacing

**File:** `src/dogen/adapters/planning_fs.py:343`
**Issue:**
Every scaffolded unit defaults its `sphinx_target` to `<unit_id>.md` at the
`docs/` root. Two units whose ids collide with an existing top-level docs page
(e.g. `index`) would, on draft, overwrite it. Minor for the skeleton (operator
edits the field), but worth a default that lands under a subdir (e.g.
`f"{unit_id}/index.md"` or a `drafts/` prefix) to reduce footguns.
**Fix:** Default to a namespaced target and/or warn on draft when the target is
an existing non-unit page.

### IN-03: `git_identity._default_runner` swallows nonzero exit, conflating "unset" with "git missing"

**File:** `src/dogen/adapters/git_identity.py:43-58`
**Issue:**
`subprocess.run(..., check=False)` returns `completed.stdout.strip()` and never
inspects `returncode` or `stderr`. If `git` is not installed, or the cwd is not
a repo, the command exits nonzero with empty stdout, which is reported to the
caller as "identity unset" — a misleading `GitIdentityError` message ("set
user.name and user.email") for what is actually a missing-git / not-a-repo
condition. Acceptable for the skeleton; the message could misdirect a user.
**Fix:** Distinguish `FileNotFoundError` (git absent) and nonzero exit from a
genuinely empty value, and surface the underlying cause in the error message.

### IN-04: Tests reach into OTel private state (`trace._TRACER_PROVIDER_SET_ONCE._done`)

**File:** `tests/test_orchestrator_hitl.py:55`, `tests/test_observability_correlation.py:51`
**Issue:**
Both fixtures poke `trace._TRACER_PROVIDER_SET_ONCE._done = False` (a private
OTel implementation detail) to re-install a tracer provider. This is flagged
with `# noqa: SLF001` and is a known test-only hack, but it is brittle across
OpenTelemetry releases — an internal rename would break the suite silently
(fixture stops resetting, spans leak across tests). Not a product bug, but a
maintenance liability in the test harness for the phase's observability proof.
**Fix:** Prefer a supported reset (e.g. construct the provider once per session,
or use OTel's documented test utilities if available) and centralize the
fixture in `conftest.py` so the single hack has one place to update.

---

_Reviewed: 2026-06-20T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
