<!-- SPDX-License-Identifier: GPL-3.0-only -->
---
kind: cross-model-review
reviewer: codex (gpt-5.x, codex-cli 0.139.0)
mode: read-only sandbox, ephemeral
scope: Phases 1-2 source (~4,700 LOC: src/dogen/**, tests/**, scripts/**, docs/conf.py, ci.yml)
relates_to: 02-REVIEW.md (Claude gsd-code-reviewer, deep)
reviewed: 2026-06-20
verdict: HIGH — block on D-25 mock-path import leak + AC5 audit-integrity gaps
findings: { new_blocker: 2, confirmed_prior_warnings: 5, new_miss_secondary: 1 }
---

# Codex Cross-Model Review — Phases 1–2

> Independent second opinion requested alongside the Claude deep review (`02-REVIEW.md`).
> Codex confirmed all 5 of Claude's WARNING findings and surfaced 2 additional BLOCKER-class
> issues Claude missed. The orchestrator addendum below records that those additive findings
> were re-verified against the live code by the orchestrator.

## Raw Codex output

**Verdict** — HIGH risk; block on D-25 mock-path import leakage and AC5 audit integrity gaps.

**Independent Findings**

- BLOCKER — `src/dogen/cli/main.py:185` — `except _backend_unavailable_error()` imports `dogen.adapters.copilot` while matching any non-HITL draft exception. On `--provider mock`, a missing unit or bad unit can load the Copilot adapter before the later `FileNotFoundError/ValueError` handler runs. Replace with a provider-neutral core exception, or catch generic exceptions and only import/check Copilot errors when `provider == "copilot"`.

- BLOCKER — `src/dogen/core/orchestrator.py:273` — `Generation.context_origins` is documented as “what the agent actually read,” but the orchestrator copies `Unit.sources` into it and always records `tools_used=[]`. For the real Copilot path this is fabricated audit evidence. Add observed context/tools to `DraftResult` or another provider result structure; if the SDK cannot report it, record an explicit unknown/empty value instead of claiming requested sources were read.

- WARNING — `.dogen/units/cli-reference/unit.md:10` — committed `unit.md` says `status: pending`, while `.dogen/units/cli-reference/progress.yaml:3` says `state: reviewed`. Code also never updates `Unit.status` when progress changes (`src/dogen/core/orchestrator.py:302`, `src/dogen/cli/main.py:263`). Remove the duplicate field or update it transactionally with progress.

- WARNING — `src/dogen/core/orchestrator.py:236` — draft/provenance/progress are written as separate plain writes (`planning_fs.py:207`, `planning_fs.py:448`). An interruption can leave a draft without provenance, provenance without progress, or a partial YAML file. Use per-file temp+`os.replace`, and preferably a store-level transaction/journal for the multi-artifact draft/review operations.

- WARNING — `src/dogen/cli/main.py:141` — `steer` unconditionally overwrites `provenance.steering`. If run after a draft, the new `steering.at` can be later than `generations[0].at`, invalidating the HITL ordering audit. Refuse to overwrite steering once generations exist, or model steering as immutable events.

- WARNING — `src/dogen/adapters/copilot/mapping.py:65` — missing `content` defaults to `""`, but explicit `content=None` is passed into `DraftResult.text` and raises a Pydantic validation error. Validate/coerce at the adapter boundary and surface a handled `BackendUnavailableError` or equivalent.

**Adjudication Of Prior Findings**

- WR-01 — CONFIRMED. Python evaluates the `except _backend_unavailable_error()` expression during exception matching. Since that helper imports `dogen.adapters.copilot` (`main.py:208`), mock-path errors other than `SteeringRequiredError` can pull in the SDK adapter before reaching `FileNotFoundError/ValueError`.

- WR-02 — CONFIRMED. `Unit.status` is documented as a progress mirror (`models.py:125`, `models.py:145`), but no write path updates `unit.md`. The committed dogfood artifact is inconsistent: `unit.md:10` pending vs `progress.yaml:3` reviewed.

- WR-03 — CONFIRMED. The draft path writes the draft, then provenance, then progress (`orchestrator.py:236-239`, `orchestrator.py:324`) using non-atomic `write_text`. Review has the same split between provenance and progress (`main.py:258`, `main.py:268`).

- WR-04 — CONFIRMED. `steer` loads or initializes provenance and then assigns `provenance.steering = ...` without checking existing generations (`main.py:141-145`). That can overwrite the original pre-draft steering event.

- WR-05 — CONFIRMED. `getattr(data, "content", "")` does not guard explicit `None`; `DraftResult(text=None, ...)` fails validation, and provider error handling does not catch that path as backend-unavailable.

Prior model missed the fabricated `context_origins/tools_used` provenance issue, which is a direct AC5 audit problem. It also missed that unknown provider errors are raised before the `draft` command’s `try` block because `select_provider(provider)` runs during `DraftRequest` construction.
---

## Orchestrator verification addendum (additive findings checked against code)

- **BLOCKER — fabricated `context_origins` / `tools_used`** — VERIFIED.
  `src/dogen/core/orchestrator.py:273-274` sets `context_origins=[s.path or s.ref or "" for s in unit.sources]`
  and `tools_used=[]`. This directly violates documented decision **D-37** (02-01 SUMMARY:
  "Unit.sources (human-pointed) vs Generation.context_origins (agent-read) never collapse").
  Harmless for the mock provider (reads nothing) but records fabricated read-context + empty
  tool-usage on the real Copilot path — an AC5 audit-integrity defect. Missed by `02-REVIEW.md`.

- **WARNING — unknown `--provider` escapes the draft try-block** — VERIFIED.
  `select_provider()` (`src/dogen/adapters/mock_provider.py:160`) raises `ValueError` on an unknown
  name, but it is called at `src/dogen/cli/main.py:175` during `DraftRequest` construction, *before*
  the `try:` at line 180. The `except (FileNotFoundError, ValueError)` handler at line 188 cannot
  catch it → unhandled traceback instead of the intended clean exit-2 message. UX defect.

- **WR-01..WR-05** — all independently CONFIRMED by Codex with matching line references; see raw output.
