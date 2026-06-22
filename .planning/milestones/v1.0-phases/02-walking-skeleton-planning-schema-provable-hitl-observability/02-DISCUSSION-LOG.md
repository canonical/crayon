# Phase 2: Walking Skeleton, Planning Schema, Provable HITL & Observability - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-19
**Phase:** 2-Walking Skeleton, Planning Schema, Provable HITL & Observability
**Areas discussed:** Observability backend, Provider proof & run-path, Planning-dir & dogfood target, Steering UX + HITL + output, Command surface (deep-dive), F1 schema fields (deep-dive)

---

## Area selection

User selected **all four** presented gray areas, and volunteered a steer on the dogfood target:
> "I need a test run; dogfooding this repo seems to be the best idea but I need to exclude .planning obviously"

This locked D-30/31/32 (dogfood this repo; `.planning/` excluded from source-lookup and output).

---

## Observability backend

| Option | Description | Selected |
|--------|-------------|----------|
| Logfire, local mode | Pydantic-native, OTel-based, fully local (send_to_logfire off → console); best DX, one vendor dep | ✓ |
| Pure OTel + console exporter | Stdlib OTel SDK + ConsoleSpanExporter; zero product dep, rougher DX | |
| OTel API now, pick backend at planning | Wire vendor-neutral OTel API; defer concrete exporter to planning | |

**User's choice:** Logfire, local mode.
**Notes:** Core instruments via the OTel API regardless, so OBS-01 ("not the SDK's telemetry") holds and the backend stays swappable (D-20). Run↔provenance correlation via shared `run_id` (D-22). → D-21.

---

## Provider proof & run-path

| Option | Description | Selected |
|--------|-------------|----------|
| Both: mock in CI + real local smoke | Mock = deterministic CI proof of port + loop; real SDK = manual local smoke, out of CI (#1606 risk) | ✓ |
| Real Copilot is the headline demo | E2E acceptance runs against real Copilot locally; needs CLI auth | |
| Mock only for v1 | Defer real SDK wiring entirely (would push SKEL-05/SC2 later) | |

**User's choice:** Both — mock in CI + real local smoke.
**Notes:** SEAM-04 kept design-only; the mock IS the second provider proving swap (D-26). Real `github-copilot-sdk==1.0.2` + pinned CLI lands here (D-27); smoke test gates SDK/CLI bumps (D-24). → D-23/24/25/26/27.

---

## Planning-dir & dogfood target

| Option | Description | Selected |
|--------|-------------|----------|
| `.dogen/units/` audit + draft under `docs/` | Audit YAML/MD in `.dogen/units/<id>/`; MyST `.md` in `docs/`; `.planning/` excluded | ✓ |
| Everything under `docs/units/` | Co-locate audit next to draft; mixes audit YAML into publishable dir | |
| Separate `drafts/` root | All output under `drafts/`; manual move into `docs/` | |

**User's choice:** `.dogen/units/` + draft under `docs/`.
**Notes:** Reinforced by the user's volunteered constraint to exclude `.planning/` (GSD's dir). Unit = a reference/explanation page about dogen drafted from `src/dogen/` + `README`/`AGENTS.md`. → D-30/31/32/33.

---

## Steering UX + HITL + output (Sphinx proof)

| Option | Description | Selected |
|--------|-------------|----------|
| Real minimal Sphinx build in CI | Stand up `docs/conf.py` + `.readthedocs.yaml` (MyST + colon_fence); CI builds the page | ✓ |
| Emit valid MyST, no build yet | Validate MyST well-formedness; defer Sphinx project/CI build | |
| Sphinx build, local-only | Stand up toolchain; keep build out of CI | |

**User's choice:** Real minimal Sphinx build in CI.
**Notes:** Resolves Phase-1 deferral D-17; "Sphinx-publishable" proven, not asserted (D-43). Steering UX / output defaults (`dogen` subcommands, git-config author capture, MyST→`docs/`) were stated as locked recommendations the user accepted.

---

## Command surface (deep-dive)

### What counts as "recorded steering" (HITL gate)

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit `dogen steer` event | Operator edits unit.md, runs `dogen steer` → stamps author+timestamp; draft refuses without it | ✓ |
| Implicit capture at `dogen draft` | Draft stamps author+timestamp at draft time | |
| Front-matter only, no stamping | Non-empty intent+audience enough; attribution from git history | |

**User's choice:** Explicit `dogen steer` event — strongest AC5 audit (steering provably precedes the draft). → D-39/40/41.

### How the operator defines a unit

| Option | Description | Selected |
|--------|-------------|----------|
| Scaffold unit.md, operator edits | `dogen unit new <id>` writes editable template; file IS the steering artifact | ✓ |
| Interactive wizard | Prompts per field, generates unit.md | |
| Flags only, one shot | `dogen draft --intent ... --audience ...`; no standing artifact | |

**User's choice:** Scaffold unit.md, operator edits. → D-35/42.

---

## F1 schema fields (deep-dive)

### Where PLAN-07 verification fields live

| Option | Description | Selected |
|--------|-------------|----------|
| Reserved block in provenance.yaml | `verification:` section, steps: [] with {id, state, evidence, env_fingerprint}; empty at v0 | ✓ |
| Dedicated verification.yaml | Separate reserved file per unit | |
| Reserved keys in progress.yaml | Fold next to lifecycle states | |

**User's choice:** Reserved block in provenance.yaml. → D-36.

### Reviewer edits (PLAN-05)

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal `dogen review` records entry | Appends {at, reviewer, summary}, advances progress to 'reviewed' | ✓ |
| Reserve the field only for v1 | Field present, populated manually/later; no command | |

**User's choice:** Minimal `dogen review` records entry — PLAN-05/06 exercised end-to-end. → D-38/42.

---

## Claude's Discretion

- OTel span names/attributes and Logfire config details.
- Mock provider's (deterministic) canned draft content/shape.
- Provider-selection precedence (flag vs env vs config).
- Exact `unit.md` scaffold template wording.
- Progress/streaming UX during a draft run.
- Smoke-test harness layout and SDK/CLI bump gating.
- Keeping the Phase-1 AST seam check alongside `import-linter` (D-29).
- Sub-module layout inside `core/` and `adapters/` per ARCHITECTURE.md.

## Deferred Ideas

- Steering layering org→repo→writer (STEER-01) — v2.
- Type-aware breadth across all four intents proven — later.
- SDLC connectors (CONN-01; `sources[].ref` reserved) — later.
- DOCPR-2822 `QaHook` extension point (CONN-03) — not a v1 port.
- Singular traceable local commit (STEER-03) — `committed` reserved, tool never sets it; v2.
- Verification execution (VERIFY-01/02) — fields reserved+empty at v0 (PLAN-07).
- Real second provider adapter (OpenCode / Pydantic AI) — design-only now (D-26).
- RAG / context-augmentation — spike-gated.
- Dependency-update bot (Renovate/Dependabot) — confirm at planning whether it lands this phase (D-18 → now relevant with the SDK pin).
