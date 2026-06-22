# Phase 4: Honest observed provenance - Context

**Gathered:** 2026-06-22
**Status:** Ready for planning

> Captured in `--auto` mode: all gray areas auto-selected, each resolved to its
> recommended option (logged inline below). Decisions are grounded in
> [[live-copilot-path-findings]] (the empty `context_origins`/`tools_used` gap
> from the 2026-06-20 live run), the Phase 3 CONTEXT decisions this builds on,
> and a fresh read of the seam code + the installed `github-copilot-sdk==1.0.2`
> event surface. Review and edit before planning if any recommended default is
> wrong.

<domain>
## Phase Boundary

Pure **brownfield hardening**, **adapter-only** — closes the fourth and last
gap the first real live run surfaced. After a *successful* live draft (Phase 3
made that possible), `provenance.yaml`'s **`context_origins`** and
**`tools_used`** must be populated from the session's **observed tool-call
events** — completing the BL-01 honesty work (v1.0 stopped *fabricating* them;
v1.1 truthfully *fills* them). Two requirements:

- **PROV-01** — `context_origins` lists what the agent **actually read**,
  derived from observed tool-call events and kept **distinct** from the
  human-pointed `sources`. No longer left empty.
- **PROV-02** — `tools_used` lists the tools the agent **actually invoked**,
  derived from observed tool-call events. No longer left empty.

**Key framing — the domain plumbing already exists.** This is *not* a new
feature; it fills lists that are already modelled and already flow end-to-end:

- `DraftResult.context_origins` / `.tools_used` already exist
  (`core/models.py:416-417`) and default to empty.
- `Generation.context_origins` / `.tools_used` already exist
  (`core/models.py:251-252`); `Generation.tools_used` is documented as
  **"source-qualified tool identifiers"**.
- The orchestrator **already copies** `result.context_origins`/`tools_used`
  verbatim into the recorded `Generation` and is explicitly forbidden from
  substituting `unit.sources` (`core/orchestrator.py:284-296`, the D-37/BL-01
  comment). It will populate the audit record the moment the provider reports
  non-empty lists — **no `core/` change is needed.**

So the entire implementation surface is the single Copilot adapter:
`src/dogen/adapters/copilot/provider.py` (observe the events) and
`mapping.py` (translate observed events → the two domain lists), plus new
unit tests against the fake/stub SDK. The orchestrator, ports, and the domain
models stay **unchanged in shape**.

**Out of scope (from REQUIREMENTS.md — do not creep):** backfilling /
re-running old v1.0 provenance; an always-on live CI provenance assertion
(live path stays manual-only, D-24); broadening the agent toolset beyond
`grep`/`glob`/`view`; recording tool *outputs*/results or content hashes
(PROV only needs read *origins* + tool *identifiers*); model discovery; any
commit/push/PR/build/publish step.

**Verification model:** a unit test against a fake/stub SDK that **emits
tool-call events** (criterion 4) — extending the established `_StubClient`
harness — **plus** one manual live run to confirm a real session populates the
lists. No CI live-call gate (D-24).

</domain>

<decisions>
## Implementation Decisions

### PROV-01/02 — observing tool-call events

- **D-01: Observe via `session.get_events()` after the turn completes.**
  `[auto]` `CopilotSession.get_events() -> list[SessionEvent]` returns the
  **complete chronological session history** (user messages, assistant
  responses, **tool executions**, …). The recommended shape is: keep the
  existing blocking `await session.send_and_wait(prompt, …)` exactly as-is,
  then — still inside the `async with session` block — call
  `session.get_events()`, filter for the tool-execution event(s), and feed them
  to the mapping translation alongside the final assistant event.
  - **Recommended over** the streaming `on_event=` callback collector and the
    `hooks=SessionHooks(pre_tool_use/post_tool_use)` callbacks because: it is
    the **least invasive** (no mutable collector threaded through a callback, no
    new SDK handler wiring, the `send_and_wait` flow is untouched), the history
    is **authoritative** ("what actually happened"), and it stays trivially
    inside the adapter seam. The hooks path also *intercepts/can modify* tool
    use, which is more power than observation needs.
  - **Research item (see Open Research Items):** confirm whether the per-tool
    payload lives on `TOOL_EXECUTION_START` vs `TOOL_EXECUTION_COMPLETE`, and
    the exact `SessionEvent.data` attribute path to the
    `ToolInvocation`. `ToolInvocation` is a dataclass carrying
    `tool_name`, `arguments`, `tool_call_id`, `session_id` — the clean carrier
    for both lists.

- **D-02: `context_origins` = the concrete file paths a *content-read* tool
  actually opened, de-duplicated in first-seen order.** `[auto]` Derive origins
  from the path argument(s) of read tools (primarily `view`) in
  `ToolInvocation.arguments`. `grep`/`glob` are discovery/query tools whose hits
  are not guaranteed-read content, so a bare search **contributes to
  `tools_used` but not to `context_origins`** unless it yields a concrete read
  path. **Omit-on-doubt:** if an invocation's arguments don't resolve to a
  concrete path, it does not add a context origin. This keeps `context_origins`
  **distinct from the human-pointed `sources`** (PROV-01 criterion 2) — it
  records what was *read*, never what was *pointed at*.

- **D-03: `tools_used` = source-qualified `builtin:<tool_name>` identifiers,
  de-duplicated in first-seen order.** `[auto]` Match the **already-asserted
  convention** in the existing tests (`tools_used=["builtin:view"]` /
  `["builtin:grep"]` in `test_orchestrator_hitl.py` and `test_models.py`) and
  the `Generation.tools_used` "source-qualified" docstring. Map
  `ToolInvocation.tool_name` → `builtin:<name>`. For the READONLY allowlist
  (`grep`/`glob`/`view`, all built-in) the `builtin:` qualifier is correct;
  a non-builtin source (none in v1.1's toolset) is a research/omit-on-doubt
  edge, not a v1.1 concern.

- **D-04: Collect in the provider, translate in a pure `mapping.py` helper —
  the seam holds.** `[auto]` `provider._run_draft` gathers the SDK events
  (`list[SessionEvent]` / `ToolInvocation`); a pure function in `mapping.py`
  (the sanctioned single translation point) converts them to the two
  **domain** `list[str]` and attaches them to the `DraftResult`
  (extend/replace `to_draft_result`'s output, or add a sibling helper). **No
  `copilot`/SDK shape crosses into `core/`** (SEAM-01/03, enforced by the AST
  guard + import-linter). Rejected: doing the path/name extraction in
  `provider.py` inline (splits the translation across two files and muddies the
  one-translation-point rule) or in `core/` (would import SDK shapes — a seam
  violation).

- **D-05: Honest-empty stays honest.** `[auto]` When **no** tool-execution
  events are observed (the agent drafted from the prompt alone, or the history
  carries none), `context_origins`/`tools_used` remain **empty** — never
  fabricated, never back-filled from `sources` (BL-01). Phase 4 only *fills*
  the lists when there is real observed evidence; the existing honest-empty
  contract and its regression test
  (`test_generation_does_not_fabricate_context_origins`) must keep passing.

### Verification (PROV criterion 4)

- **D-06: Extend the `_StubClient` fake-SDK harness to emit tool-call events.**
  `[auto]` The stub session's `get_events()` returns a scripted sequence of
  fake tool-execution `SessionEvent`s (e.g. a `view README.md` + a `grep`)
  alongside the final assistant message; the test asserts the resulting
  `DraftResult.context_origins` == the read paths and `.tools_used` ==
  `["builtin:view", "builtin:grep"]` (first-seen, de-duped), and that the
  recorded `Generation` carries them. Add a **focused unit test on the pure
  `mapping.py` translation** (events → the two lists) so the derivation logic is
  pinned independently of the session plumbing. Recommended over an
  end-to-end-only live assertion — the live path stays manual (D-24), so the
  fake-SDK test is the CI-runnable proof.

### Claude's Discretion

- Exact extraction details left to planner/executor within the decisions above:
  the precise argument-key lookup per tool (`path`/`file`/…) after research
  confirms them; whether `to_draft_result` is extended in place or paired with a
  new `tool_events_to_provenance(...)` helper; the precise fake `SessionEvent`
  construction in the stub (mirroring whatever the research confirms the real
  event shape to be).
- Whether `grep`/`glob` that *name a concrete file* (vs a directory/pattern)
  should add a context origin — omit-on-doubt default is "no", but a tightly
  scoped, well-tested inclusion is acceptable if research shows the argument
  reliably carries a single read path.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Scope & requirements (read first)
- `.planning/ROADMAP.md` — Phase 4 goal, the **4 success criteria**, the
  PROV-01/02 mapping, and the v1.1 manual-only **D-24** constraint.
- `.planning/REQUIREMENTS.md` — full **PROV-01/02** text *and* the **Out of
  Scope** table (backfilling old provenance, live CI gate, toolset broadening —
  all excluded).
- `.planning/phases/03-live-copilot-path-runs-out-of-the-box/03-CONTEXT.md` —
  the Phase 3 decisions this builds on: the seam rules (SDK types only under
  `adapters/copilot/`, `mapping` is the one translation point), the
  `approve_all` read-only permission handler (D-04 there) that lets the agent
  read at all, and the explicit **deferred note** that PROV-01/02 are Phase 4.

### Implementation surface (the code this phase changes)
- `src/dogen/adapters/copilot/provider.py` — `_run_draft` (the
  `async with session` block, lines ~263-283) is where `get_events()` is read
  right after `send_and_wait`; `to_draft_result(event, run_id="")` is called in
  `_require_assistant_message` (line ~347). **Both lists land here via mapping.**
- `src/dogen/adapters/copilot/mapping.py` — `to_draft_result` (the sole seam
  translation, lines 42-81): gains the observed `context_origins`/`tools_used`
  (D-04). The pure events→lists helper lives here.
- `src/dogen/adapters/copilot/tools.py` — the `READONLY` allowlist
  (`grep`/`glob`/`view`): the closed set of tool names whose invocations are
  observed and qualified `builtin:` (D-03). Do not broaden.
- `src/dogen/core/models.py` — `DraftResult.context_origins/tools_used`
  (lines 416-417) and `Generation.context_origins/tools_used`
  (lines 251-252, the "source-qualified" docstring). **Fields already exist —
  do NOT change their shape.**
- `src/dogen/core/orchestrator.py` — `_record_generation` (lines 250-297):
  already copies `result.context_origins`/`tools_used` verbatim and is
  forbidden from substituting `sources` (D-37/BL-01). **Confirm no change is
  needed** — populating the provider's lists is sufficient.

### Test patterns to extend
- `tests/test_copilot_backend_unavailable.py` — the `_StubClient` +
  `monkeypatch.setattr("…provider.CopilotClient", factory)` fake-SDK pattern
  (lines 60-97). The new PROV test extends it so the stub session's
  `get_events()` emits tool-call events.
- `tests/test_orchestrator_hitl.py` (lines ~225-270) — the existing honesty
  tests: `test_generation_does_not_fabricate_context_origins` (must keep
  passing, D-05) and the case asserting `context_origins=["docs/actually_read.md"]`
  / `tools_used=["builtin:view"]` — the exact format the new derivation must
  produce.
- `tests/test_models.py` (lines ~136-153) — the
  `sources`-vs-`context_origins` distinctness test and the `builtin:grep`
  identifier format.

### Empirical source (not a repo file)
- Memory `[[live-copilot-path-findings]]` — the "empty
  `context_origins`/`tools_used`" gap from the 2026-06-20 live run (account
  `akcano`, CLI `1.0.64-0`, SDK `github-copilot-sdk==1.0.2`) that PROV-01/02
  close.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`to_draft_result` seam translator** (`mapping.py`): the one place SDK event
  shapes become domain `DraftResult` — extend it (or add a sibling pure helper)
  to also emit the two observed lists. Reuse, don't bypass.
- **`_StubClient` fake-SDK harness** (`tests/test_copilot_backend_unavailable.py`):
  the established no-network unit-test pattern; the PROV test scripts its
  session's `get_events()` to emit tool-call events.
- **`DraftResult` / `Generation` provenance fields** (`core/models.py`): already
  modelled and defaulted-empty; Phase 4 fills them, adds no domain shape.
- **Orchestrator verbatim copy** (`core/orchestrator.py:284-296`): already wires
  `result.*` → `Generation.*` and bans the `sources` fallback (BL-01) — the
  populated lists flow to `provenance.yaml` with zero core changes.

### Established Patterns
- **Anti-corruption seam (SEAM-01/03):** `copilot`/SDK types
  (`SessionEvent`, `ToolInvocation`) may be imported **only** under
  `adapters/copilot/`; `mapping` is the single translation point. The observed
  events must be converted to plain `list[str]` *inside the adapter* — an AST
  seam guard + import-linter contract enforce it (`tests/test_seam*.py`).
- **Honest provenance (BL-01/D-37):** record only what was observed; empty when
  nothing was, never fabricate or copy `sources`. Phase 4 fills the lists
  *because* there is now real observed evidence — it does not relax the rule.
- **Manual-only live path (D-24):** verified by a fake/stub-SDK unit test
  (CI-runnable) plus one manual live run; no live CI gate.

### Integration Points
- `provider._run_draft`: `await session.send_and_wait(...)` → (new)
  `events = session.get_events()` → `mapping`(final event + tool events) →
  `DraftResult(context_origins=…, tools_used=…)` → orchestrator
  `_record_generation` (verbatim) → `provenance.yaml` `generations[]`.

</code_context>

<specifics>
## Specific Ideas

- The acceptance bar is concrete: after a successful live draft, the recorded
  `generations[].context_origins` is **non-empty** and reflects the source
  file(s) the agent `view`-ed, and `tools_used` is **non-empty** and lists the
  built-in tools it ran — both kept distinct from the unit's `sources`.
- Phase 4 is jointly meaningful only on top of Phase 3's working live draft:
  the same live run that proved a Claude-family draft (Phase 3 criterion 3) is
  the run whose tool-call events Phase 4 records.

### Open Research Items (for gsd-phase-researcher)
1. **Tool-event type + data shape** — `get_events()` returns
   `list[SessionEvent]`; confirm whether the `ToolInvocation` (tool name +
   arguments) rides on `TOOL_EXECUTION_START` vs `TOOL_EXECUTION_COMPLETE`
   (both exist in `SessionEventType`), and the exact `SessionEvent.data`
   attribute path to reach it. Confirm `get_events()` after `send_and_wait`
   reliably includes the just-completed turn's tool events (vs needing the
   `on_event=` streaming collector as a fallback).
2. **Per-tool argument keys** — confirm the `ToolInvocation.arguments` dict keys
   for `view` (the read path), and for `grep`/`glob`, so D-02's path extraction
   reads the right field; omit-on-doubt when absent.
3. **Tool source/namespace qualifier** — confirm whether the SDK reports a tool
   source so `tools_used`'s `builtin:` qualifier (D-03) could be *derived*
   rather than hardcoded. For the v1.1 READONLY built-in allowlist, hardcoded
   `builtin:` is correct; this only matters if a future non-builtin tool appears.

</specifics>

<deferred>
## Deferred Ideas

- **Recording tool *outputs* / results / content hashes** in provenance — PROV
  only needs read *origins* and tool *identifiers*; capturing what each tool
  *returned* is future evidence/verification work (the reserved `verification`
  block), not v1.1.
- **Treating `grep`/`glob` match results as `context_origins`** — v1.1 counts
  only concrete content-reads (`view`); a richer "search hit ⇒ origin"
  derivation is deferred.
- **Backfilling / re-running old v1.0 provenance** — explicitly out of scope
  (REQUIREMENTS Out of Scope); v1.1 fixes the path forward only.
- **An always-on live CI provenance assertion** — the live path stays
  manual-only (D-24); the fake-SDK unit test is the CI-runnable proof.

None of these are acted on in Phase 4.

</deferred>

---

*Phase: 4-honest-observed-provenance*
*Context gathered: 2026-06-22*
