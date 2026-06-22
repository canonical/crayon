# Phase 3: Live Copilot path runs out of the box - Context

**Gathered:** 2026-06-22
**Status:** Ready for planning

> Captured in `--auto` mode: all gray areas auto-selected, each resolved to its
> recommended option (logged inline below). Decisions are grounded in the live
> findings memory ([[live-copilot-path-findings]], 2026-06-20 run, account
> `akcano`, CLI `1.0.64-0`, SDK `github-copilot-sdk==1.0.2`) and a fresh read of
> the actual seam code + installed SDK. Review and edit before planning if any
> recommended default is wrong.

<domain>
## Phase Boundary

Pure **brownfield hardening** of the existing live `dogen draft --provider copilot`
path — **no net-new domain features**. The phase closes the four gaps the first
real live run surfaced so the path runs end-to-end out of the box, across five
requirements:

- **LIVE-01** — operator can pick the model (`--model`), and the bare-command
  default is a model that actually exists on a standard Copilot account (the
  hardcoded, unavailable `gpt-5` default is retired).
- **LIVE-02** — a non-interactive run can actually read the human-pointed
  sources: the provider supplies a permission handler that auto-approves the
  already-read-only `grep`/`glob`/`view` lookups instead of having them denied.
- **LIVE-03** — drafting succeeds on **any** available model family: the
  provider sends `reasoning_effort` only to models that accept it (GPT-5 family)
  and omits it for Claude-family models that reject it.
- **ERR-01** — a backend model rejection prints a clear message naming the
  rejected model and exits nonzero — never a raw `JsonRpcError` traceback
  (closes accepted v1.0 debt item #4).
- **ERR-02** — any other live backend / JSON-RPC error on the draft path is
  classified into a handled failure with a clear message and nonzero exit —
  never an uncaught crash.

The entire implementation surface is the single Copilot adapter
(`provider.py`, `mapping.py`, `tools.py`) plus the existing provider-selection
seam (`mock_provider.select_provider`) and the thin CLI (`cli/main.py`). The
orchestrator/ports stay untouched in shape (the `Effort`/`DraftRequest.effort`
field already exists).

**Out of scope (from REQUIREMENTS.md — do not creep):** model auto-discovery /
a "list models" subsystem; an always-on live CI smoke test (live path stays
manual-only, D-24); interactive/streaming permission prompts; broadening the
agent toolset beyond `grep`/`glob`/`view`; backfilling old provenance; any
commit/push/PR/build/publish step. **PROV-01/02 (populating
`context_origins`/`tools_used` from observed events) belong to Phase 4** — this
phase only makes a successful live draft *possible*.

**Verification model:** manual live runs **plus** unit tests against a fake/stub
SDK (extending `tests/test_copilot_backend_unavailable.py`). No CI live-call gate.

</domain>

<decisions>
## Implementation Decisions

### LIVE-01 — model selection & new default

- **D-01: New default model = `gpt-5-mini`.** `[auto]` Recommended over the
  Claude options because it stays in the GPT-5 family — so the LIVE-03
  reasoning-effort happy path is still exercised by the default run — and it is
  the exact model that produced a real source-grounded MyST reference page in
  the 2026-06-20 live test. Confirmed available on a standard account (probed
  set: `gpt-5-mini`, `claude-sonnet-4.5`, `claude-haiku-4.5`). Replaces
  `_DEFAULT_MODEL = "gpt-5"` in `provider.py`.
- **D-02: Add a `--model` option to `dogen draft`** (Typer `Option`, defaults to
  `None` → provider falls back to its `gpt-5-mini` constant). Mirrors the
  existing `--provider` option shape.
- **D-03: Thread the chosen model through `select_provider`.** `[auto]` Extend
  `select_provider(name, *, model=None, effort=None)`; each factory accepts the
  kwargs — the mock factory **ignores** them (stays SDK-free, deterministic),
  the copilot factory forwards them to `CopilotDraftingProvider(model=…)`. Keeps
  the dict-dispatch + lazy import (D-25) intact; the mock path never imports the
  SDK. Rejected: building the provider directly in the CLI (would duplicate the
  by-name dispatch and risk eager SDK import).

### LIVE-02 — permission handler

- **D-04: Wire `on_permission_request=PermissionHandler.approve_all`** on
  `create_session` (import `from copilot.session import PermissionHandler`).
  `[auto]` Recommended over a custom allowlist-checking handler because it is
  **safe by construction**: only `grep`/`glob`/`view` are even available
  (`READONLY` allowlist) and every write/exec/network tool is both unavailable
  and on the `DENY` denylist, so `approve_all` can only ever approve a read-only
  request. A custom handler would re-implement a guarantee the toolset already
  enforces (SKEL-04/D-28). Note: the SDK only sends permission requests at all
  when a handler is provided (`requestPermission` is gated on its presence), so
  this is what unblocks the source reads.

### LIVE-03 — family-aware `reasoning_effort`

- **D-05: Gate `reasoning_effort` with a hardcoded GPT-5-family heuristic.**
  `[auto]` Send `reasoning_effort` only when the chosen model is GPT-5 family;
  omit it entirely for everything else (Claude, unknown). Recommended over
  querying `client.list_models()` → `ModelInfo.supports.reasoning_effort`
  because: it matches the ROADMAP framing ("sent only to GPT-5-family models"),
  adds no network round-trip, is forward-safe (an unknown model omits the
  param rather than erroring), and avoids brushing the out-of-scope
  "model discovery" line. The exact family-match predicate (prefix `gpt-5` vs a
  small allowlist) is a research/planning detail — the **decision is the
  heuristic approach, omit-on-doubt.** See Open Research Items for the
  capability-API alternative the researcher should note but not adopt.

### ERR-01 / ERR-02 — clean live-error mapping

- **D-06: Two handled error types, both `RuntimeError` subclasses.** `[auto]`
  Add a **dedicated model-rejection error** (ERR-01, names the model) and
  **broaden the existing `BackendUnavailableError`** to also wrap other
  draft-path `JsonRpcError`s (ERR-02). Both subclass `RuntimeError` so the CLI's
  existing `except RuntimeError` + `type(exc).__name__` classification keeps the
  `--provider mock` path from ever importing `adapters/copilot/` (D-25). Both
  exit nonzero (exit 1). Rejected: one error with branchy messages (loses the
  CLI's clean by-name dispatch and the model-specific message ERR-01 wants).
- **D-07: Name the rejected model from what we already requested, not by parsing
  the backend string.** `[auto]` The provider already holds `self._model`;
  detect "model rejected" by the `JsonRpcError` shape (`code == -32603` + the
  not-available signature) but report `self._model` in the user-facing message,
  appending the backend's own message for detail. Robust to backend
  message-format drift; no fragile regex. CLI renders e.g.
  `Model 'gpt-5' was rejected by the backend: <detail>` and exits nonzero.
- **D-08: Catch `JsonRpcError` inside the adapter (the sanctioned SDK-import
  site), converting it to the handled domain errors above.** It is currently
  NOT caught (only `StopError`/`ConnectionError`/`OSError`/`TimeoutError` are),
  which is exactly why the `-32603` escapes as a raw traceback today. See Open
  Research Items — `JsonRpcError` import path is private.

### Claude's Discretion

- Exact GPT-5-family match predicate (D-05) and the precise wording of the
  ERR-01/02 user messages (D-07) — planner/executor choose, within the
  decisions above.
- Whether `select_provider`'s new `effort` kwarg is wired now or left for a
  later `--effort` option — model is the LIVE-01 requirement; effort threading
  is optional scaffolding (the `Effort` enum + per-pass default already exist).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Scope & requirements (read first)
- `.planning/ROADMAP.md` — Phase 3 goal, the 5 success criteria, and the
  LIVE-01/02/03 + ERR-01/02 requirement mapping (and the v1.1 manual-only D-24
  constraint).
- `.planning/REQUIREMENTS.md` — full LIVE-01/02/03 + ERR-01/02 text *and* the
  **Out of Scope** table (model discovery, live CI gate, interactive permission
  UI, toolset broadening — all excluded).

### Implementation surface (the code this phase changes)
- `src/dogen/adapters/copilot/provider.py` — session open + the **only** place
  the model/effort/permission-handler are passed to `create_session`, and the
  `try/except` that converts backend failures to handled errors (LIVE-01/02/03,
  ERR-01/02 all land here). Note `_DEFAULT_MODEL = "gpt-5"` (line 62), the
  unconditional `reasoning_effort=self._effort.value` (line 171), and the
  `except` list that omits `JsonRpcError` (lines 138–145).
- `src/dogen/adapters/copilot/tools.py` — the `READONLY` allowlist / `DENY`
  denylist that make D-04 (`approve_all`) safe by construction. Do not broaden.
- `src/dogen/adapters/mock_provider.py` — `select_provider` + the
  `_PROVIDER_FACTORIES` dict-dispatch and the lazy `_make_copilot_provider`
  (D-25). Where D-03 model-threading lands; the mock factory must keep ignoring
  model/effort.
- `src/dogen/cli/main.py` — the `draft` command: add `--model` (D-02), keep the
  `except RuntimeError` by-name classification (D-06) that renders clean exits.
- `src/dogen/adapters/copilot/__init__.py` — the sanctioned SDK-import site and
  the adapter's public `__all__` (new error type gets exported here).
- `src/dogen/core/orchestrator.py` / `src/dogen/core/ports.py` — unchanged in
  shape; confirm `DraftRequest.effort` / `Effort` already exist (they do).

### Test pattern to extend
- `tests/test_copilot_backend_unavailable.py` — the `_StubClient` +
  `monkeypatch.setattr("…provider.CopilotClient", factory)` fake-SDK pattern the
  new LIVE-02/03 + ERR-01/02 unit tests will extend (script `create_session`,
  assert session kwargs, raise a fake `JsonRpcError`).

### Empirical source (not a repo file)
- Memory `[[live-copilot-path-findings]]` — the four gaps, the probed available
  model set, and the confirmed fix shapes (`approve_all`, per-family effort).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`select_provider` dict-dispatch + lazy copilot factory** (`mock_provider.py`):
  the seam where `--model` threads through; extend its signature, don't replace it.
- **`READONLY`/`DENY` ToolSets** (`tools.py`): the security boundary that makes
  `approve_all` safe — reuse as-is, the decision is to lean on them, not change them.
- **`_StubClient` fake-SDK harness** (`tests/test_copilot_backend_unavailable.py`):
  the established no-network unit-test pattern; the new tests extend it.
- **CLI `except RuntimeError` + `type(exc).__name__` classifier** (`main.py`,
  lines 227–236): already renders `BackendUnavailableError` as a clean exit-1
  without importing the SDK; the new model-rejection error plugs into the same
  classifier by name.
- **`Effort` enum + `DraftRequest.effort`** (`core/models.py`,
  `core/orchestrator.py`): effort plumbing already exists; LIVE-03 gates *whether*
  it is sent to the SDK, it does not add new domain shape.

### Established Patterns
- **Anti-corruption seam (SEAM-01/03):** `copilot`/SDK types may be imported
  **only** under `adapters/copilot/`; `mapping.to_draft_result` is the one
  translation point. New SDK symbols (`PermissionHandler`, the `JsonRpcError`
  catch) must stay inside this subtree — an AST seam guardrail + import-linter
  contract enforce it (`tests/test_seam*.py`).
- **Handled-error-not-crash (SKEL-05/D-27):** backend failures become a
  `RuntimeError` subclass the CLI maps to a nonzero exit; ERR-01/02 extend this
  same pattern across the JSON-RPC surface.
- **Lazy SDK import (D-25):** the mock/CI path must never import
  `adapters/copilot/`; preserve it when threading the model.

### Integration Points
- `cli/main.py draft()` → `select_provider(provider, model=…)` →
  `CopilotDraftingProvider(model=…)` → `create_session(model=, reasoning_effort?=,
  on_permission_request=, available_tools=READONLY, excluded_tools=DENY)`.
- Adapter `except` → raises handled error (subclass of `RuntimeError`) →
  CLI `except RuntimeError` name-classifier → `typer.Exit(code=1)`.

</code_context>

<specifics>
## Specific Ideas

- The bare `dogen draft --provider copilot` (no `--model`) must succeed on the
  new default — that's success criterion 1, so the default change and the
  `--model` option ship together.
- LIVE-02 done right means a Claude-family model selected by `--model` produces a
  real source-grounded draft (criterion 3) — the family-effort gate (D-05) and
  the permission handler (D-04) are jointly verified by one live run on a Claude
  model.

### Open Research Items (for gsd-phase-researcher)
1. **`JsonRpcError` import path is private** — it lives at `copilot._jsonrpc`
   and is **not** in the SDK's public `__all__`. The researcher must confirm
   whether a public alias/base exists; if not, decide between (a) importing the
   private symbol *inside the adapter only* (the sanctioned SDK-coupling site,
   guarded by a unit test) vs (b) duck-typing on a broad exception carrying
   `.code`/`.message`. Lean (a) with a regression test, per D-08.
2. **GPT-5-family predicate** — confirm the exact model-name shapes the backend
   returns (`gpt-5`, `gpt-5-mini`, …) so D-05's prefix/allowlist match is right;
   the SDK *does* expose `ModelInfo.supports.reasoning_effort` via
   `list_models()` as the authoritative capability source — **note it, but do
   not adopt it** (out-of-scope discovery + extra round-trip; v1.1 uses the
   heuristic).
3. **`-32603` model-not-available signature** — confirm the code/message the
   backend actually returns for a rejected model so D-07's detection is precise.

</specifics>

<deferred>
## Deferred Ideas

- **Populating `context_origins` / `tools_used` from observed tool-call events**
  — that is PROV-01/02, explicitly **Phase 4** (depends on a working live draft
  from this phase to observe). `mapping.to_draft_result` still honestly records
  empties until then.
- **Model auto-discovery / "list available models"** — out of scope for v1.1; a
  clear ERR-01 message naming the rejected model is the sanctioned substitute.
- **Interactive / streaming permission prompts** — out of scope while the toolset
  is read-only; `approve_all` is sufficient.
- **An `--effort` CLI option** — not required by any v1.1 requirement; the
  `effort` kwarg is plumbed at the seam but a user-facing flag can wait.

None of these are acted on in Phase 3.

</deferred>

---

*Phase: 3-live-copilot-path-runs-out-of-the-box*
*Context gathered: 2026-06-22*
