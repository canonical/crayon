# Phase 3: Live Copilot path runs out of the box - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-22
**Phase:** 3-live-copilot-path-runs-out-of-the-box
**Mode:** `--auto` (all gray areas auto-selected; each resolved to its recommended option)
**Areas discussed:** New default model, Model threading through the seam, reasoning_effort family gating, Error taxonomy (ERR-01/02), Naming the rejected model, Permission handler choice

---

## New default model (LIVE-01)

| Option | Description | Selected |
|--------|-------------|----------|
| `gpt-5-mini` | GPT-5 family → LIVE-03 effort path still exercised by default; produced a real source-grounded draft in the 2026-06-20 live test; confirmed available | ✓ |
| `claude-sonnet-4.5` | Available, but Claude-family default would never exercise the reasoning_effort path on a bare run | |
| `claude-haiku-4.5` | Available, cheapest, but same Claude-family caveat and lower drafting quality | |

**Auto choice:** `gpt-5-mini` (recommended default).
**Notes:** Probed available set on a standard account: `gpt-5-mini`, `claude-sonnet-4.5`, `claude-haiku-4.5`. Retires `_DEFAULT_MODEL = "gpt-5"`.

---

## Model threading through the seam (LIVE-01)

| Option | Description | Selected |
|--------|-------------|----------|
| Extend `select_provider(name, *, model=None, effort=None)` | Factories forward kwargs; mock ignores; copilot forwards to constructor — keeps dict-dispatch + lazy import (D-25) | ✓ |
| Build the provider directly in the CLI | Duplicates the by-name dispatch; risks eager SDK import on the mock path | |
| Pass a settings/config object | Heavier; over-engineered for one optional field in v1.1 | |

**Auto choice:** Extend `select_provider` signature (recommended).
**Notes:** Mock factory must keep ignoring model/effort to stay SDK-free and deterministic.

---

## reasoning_effort family gating (LIVE-03)

| Option | Description | Selected |
|--------|-------------|----------|
| Hardcoded GPT-5-family heuristic | Send effort only for GPT-5 family; omit for Claude/unknown — matches ROADMAP framing, no round-trip, forward-safe | ✓ |
| Query `list_models()` → `ModelInfo.supports.reasoning_effort` | Authoritative capability source, but adds a network round-trip and edges toward out-of-scope "model discovery" | |

**Auto choice:** Hardcoded GPT-5-family heuristic, omit-on-doubt (recommended).
**Notes:** Capability API noted for the researcher as an alternative *not* adopted in v1.1.

---

## Error taxonomy — ERR-01 vs ERR-02

| Option | Description | Selected |
|--------|-------------|----------|
| Two error types | Dedicated model-rejection error (names the model, ERR-01) + broaden `BackendUnavailableError` for other JSON-RPC errors (ERR-02); both `RuntimeError` subclasses, both exit nonzero | ✓ |
| One error with branchy messages | Loses the CLI's clean by-name classification and the model-specific ERR-01 message | |

**Auto choice:** Two error types (recommended).
**Notes:** Subclassing `RuntimeError` preserves the CLI's `except RuntimeError` + `type(exc).__name__` dispatch that keeps the mock path from importing the SDK (D-25).

---

## Naming the rejected model (ERR-01)

| Option | Description | Selected |
|--------|-------------|----------|
| Use `self._model` (already requested) | We already hold the requested model; detect rejection by `JsonRpcError` shape (code + signature) but report the known model name + backend detail — robust to message drift | ✓ |
| Regex-parse the JSON-RPC message text | Fragile to backend message-format changes | |

**Auto choice:** Use `self._model` (recommended).

---

## Permission handler choice (LIVE-02)

| Option | Description | Selected |
|--------|-------------|----------|
| `PermissionHandler.approve_all` | Safe by construction — only `grep`/`glob`/`view` are available; write/exec/network are unavailable *and* denied, so approve_all only ever sees read-only requests | ✓ |
| Custom allowlist-checking handler | Re-implements a guarantee the read-only toolset already enforces (SKEL-04/D-28) | |

**Auto choice:** `PermissionHandler.approve_all` (recommended).
**Notes:** The SDK only sends permission requests when a handler is provided, so wiring this is what unblocks the source reads.

---

## Claude's Discretion

- Exact GPT-5-family match predicate (prefix vs allowlist) and the precise wording of the ERR-01/02 user messages.
- Whether `select_provider`'s new `effort` kwarg is wired now or deferred until a future `--effort` option (no v1.1 requirement forces it).

## Deferred Ideas

- Populating `context_origins` / `tools_used` from observed tool-call events — PROV-01/02, **Phase 4**.
- Model auto-discovery / "list available models" — out of scope for v1.1.
- Interactive / streaming permission prompts — out of scope while the toolset is read-only.
- An `--effort` CLI option — no v1.1 requirement forces it.
