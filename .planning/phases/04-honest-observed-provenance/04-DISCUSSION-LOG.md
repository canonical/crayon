# Phase 4: Honest observed provenance - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-22
**Phase:** 4-honest-observed-provenance
**Mode:** `--auto` (all gray areas auto-selected; recommended option chosen per area, logged below)
**Areas discussed:** Observation mechanism, `context_origins` derivation, `tools_used` format, Seam placement, Honest-empty behaviour, Verification approach

---

## Observation mechanism — how the adapter sees the agent's tool calls

| Option | Description | Selected |
|--------|-------------|----------|
| `session.get_events()` after the turn | Keep blocking `send_and_wait`; read the complete chronological history afterward, filter tool-execution events | ✓ |
| `on_event=` streaming callback collector | Register a per-event callback on `create_session`; accumulate tool events into a mutable list | |
| `hooks=SessionHooks(pre/post_tool_use)` | Register tool-use hook callbacks carrying `ToolInvocation` | |

**Auto-selected:** `session.get_events()` post-turn.
`[auto] Observation mechanism — Q: "How should the adapter observe tool-call events?" → Selected: "session.get_events() after the turn" (recommended default)`
**Notes:** Least invasive — leaves the existing `send_and_wait` flow untouched, needs no new SDK handler wiring or threaded collector, and the history is authoritative. Hooks can also *intercept/modify* tool use (more power than observation needs). Exact event-type/`data` path flagged as an Open Research Item.

---

## `context_origins` derivation — what counts as "actually read"

| Option | Description | Selected |
|--------|-------------|----------|
| Content-read tool path args (`view`), dedup first-seen | Record concrete file paths a read tool opened; `grep`/`glob` count only as tools unless they yield a read path | ✓ |
| Every tool-call argument that looks like a path | Include `grep`/`glob` patterns/targets as origins too | |
| Mirror `sources` when reads can't be resolved | Fall back to the human-pointed sources | |

**Auto-selected:** content-read tool path args, de-duplicated, first-seen order; omit-on-doubt.
`[auto] context_origins derivation — Q: "What should context_origins record?" → Selected: "content-read tool path args (view), omit-on-doubt" (recommended default)`
**Notes:** Keeps `context_origins` distinct from `sources` (PROV-01 criterion 2) — what was *read*, not what was *pointed at*. The mirror-`sources` option is explicitly the BL-01 violation Phase 4 must never reintroduce.

---

## `tools_used` identifier format

| Option | Description | Selected |
|--------|-------------|----------|
| `builtin:<tool_name>`, dedup first-seen | Source-qualified, matching existing test assertions and the `Generation.tools_used` docstring | ✓ |
| Raw `tool_name` only | Record the bare SDK tool name | |

**Auto-selected:** `builtin:<tool_name>`, de-duplicated, first-seen order.
`[auto] tools_used format — Q: "How should tool identifiers be recorded?" → Selected: "builtin:<tool_name>" (recommended default)`
**Notes:** Matches the already-asserted convention in `test_orchestrator_hitl.py` / `test_models.py` (`builtin:view`, `builtin:grep`) and the "source-qualified" docstring. Correct for the all-builtin READONLY allowlist; deriving the qualifier from an SDK-reported source is noted as a research edge, not a v1.1 need.

---

## Seam placement — where collection/translation lives

| Option | Description | Selected |
|--------|-------------|----------|
| Collect in provider, translate in pure `mapping.py` helper | SDK shapes stay under `adapters/copilot/`; `mapping` remains the one translation point; `core/` unchanged | ✓ |
| Extract paths/names inline in `provider.py` | Do the string work in the provider directly | |
| Pass events toward `core/` and translate there | Let the orchestrator interpret events | |

**Auto-selected:** collect in provider, translate in a pure `mapping.py` helper.
`[auto] Seam placement — Q: "Where do observed events become domain lists?" → Selected: "provider collects, mapping translates" (recommended default)`
**Notes:** Honours SEAM-01/03 (SDK types only under the adapter subtree; one translation point). The `core/`-translation option would import SDK shapes — a seam violation caught by the AST guard + import-linter.

---

## Honest-empty behaviour — when nothing is observed

| Option | Description | Selected |
|--------|-------------|----------|
| Stay empty, never fabricate | If no tool events observed, both lists remain `[]` | ✓ |
| Fall back to `sources` | Populate from human-pointed sources | |

**Auto-selected:** stay empty; never fabricate, never back-fill from `sources`.
`[auto] Honest-empty — Q: "What if no tool-call events are observed?" → Selected: "stay empty (BL-01)" (recommended default)`
**Notes:** Preserves the BL-01 contract and the existing `test_generation_does_not_fabricate_context_origins` regression guard. Phase 4 fills the lists only when there is real observed evidence.

---

## Verification approach — proving PROV criterion 4

| Option | Description | Selected |
|--------|-------------|----------|
| Extend `_StubClient` to emit tool-call events + pure mapping unit test | Stub `get_events()` returns scripted tool events; assert populated lists + a focused events→lists test | ✓ |
| End-to-end live assertion only | Rely on the manual live run to prove population | |

**Auto-selected:** extend the fake-SDK harness to emit tool events, plus a focused mapping unit test.
`[auto] Verification — Q: "How is the population verified?" → Selected: "fake-SDK tool-call events + mapping unit test" (recommended default)`
**Notes:** The live path stays manual (D-24), so the fake-SDK test is the CI-runnable proof (criterion 4). The pure mapping test pins the derivation logic independently of session plumbing.

---

## Claude's Discretion

- Exact per-tool argument-key lookup (`path`/`file`/…) after research confirms the shapes.
- Whether `to_draft_result` is extended in place or paired with a new `tool_events_to_provenance(...)` helper.
- Precise fake `SessionEvent` construction in the stub (mirror the research-confirmed real event shape).
- Whether a `grep`/`glob` that names a single concrete file may add a context origin (omit-on-doubt default: no).

## Deferred Ideas

- Recording tool *outputs* / results / content hashes (future verification work; the reserved `verification` block).
- Treating `grep`/`glob` match results as `context_origins` (v1.1 counts only `view`-style reads).
- Backfilling / re-running old v1.0 provenance (out of scope — REQUIREMENTS Out of Scope).
- An always-on live CI provenance assertion (live stays manual-only, D-24).
