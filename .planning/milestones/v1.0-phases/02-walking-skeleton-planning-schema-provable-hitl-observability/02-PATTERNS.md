# Phase 2: Walking Skeleton, Planning Schema, Provable HITL & Observability - Pattern Map

**Mapped:** 2026-06-19
**Files analyzed:** 18 (new/modified)
**Analogs found:** 18 / 18 (all have at least a header/test/gate analog; 0 role+data-flow exact analogs — this is a greenfield feature phase filling empty Phase-1 stubs)

> **Read this first:** Phase 1 left only *scaffold* — empty package `__init__.py` stubs, one AST guardrail script paired with a pytest test, a CI/pre-commit gate mirror, a `pyproject.toml`, and a `canonical.jinja2` REUSE template. There is **no existing controller/service/model/adapter with real logic** to copy a role+data-flow pattern from. So the strongest, most load-bearing analogs are **cross-cutting**: the REUSE/SPDX header (every file), the single-source-of-truth gate pattern (`seam_check.py` ↔ `test_seam.py` ↔ CI ↔ pre-commit), the test layout, and the seam-import discipline. Per-file "core pattern" must come from RESEARCH.md's verified SDK API and ARCHITECTURE.md patterns — flagged per file below.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/dogen/core/models.py` | model (Pydantic v2 schema) | transform / validation | `src/dogen/core/__init__.py` (header+docstring), coding-guide §2 "real data structures" | header-only (no model analog exists) |
| `src/dogen/core/ports.py` | port (Protocol defs) | request-response (async) | `src/dogen/core/__init__.py` docstring (states "Protocol ports it defines") | header-only |
| `src/dogen/core/orchestrator.py` | service (use-case orchestration) | request-response (async, event-driven inputs) | none (greenfield) — shape from RESEARCH Pattern 3 + Arch map | header-only |
| `src/dogen/core/observability.py` | utility (OTel API helpers) | event-driven (spans/metrics) | none — RESEARCH Pattern 3 | header-only |
| `src/dogen/adapters/copilot/provider.py` | adapter (sole SDK importer) | request-response (async, streaming) | `src/dogen/adapters/copilot/__init__.py` docstring (declares this the sole import site) | header-only |
| `src/dogen/adapters/copilot/tools.py` | adapter config | config | none — RESEARCH Pattern 2 (`ToolSet`) | header-only |
| `src/dogen/adapters/copilot/mapping.py` | adapter (anti-corruption) | transform | none — RESEARCH "Code Examples / mapping.py" | header-only |
| `src/dogen/adapters/mock_provider.py` | adapter (test double, ships in prod for `--provider mock`) | request-response (async) | none — implements same `ports.DraftingProvider` | header-only |
| `src/dogen/adapters/planning_fs.py` | adapter (PlanningStore, filesystem) | file-I/O (YAML/MD read+write) | none — writes `.dogen/units/` + `docs/` | header-only |
| `src/dogen/adapters/git_identity.py` | adapter (host I/O) | request-response (shell `git config`) | none; coding-guide §5 shell-allowlist discipline | header-only |
| `src/dogen/obs/logfire_backend.py` | config (composition-root backend wiring) | config | none — RESEARCH Pattern 3 (only `logfire` import site) | header-only |
| `src/dogen/cli/main.py` | controller (Typer app, thin) | request-response | `src/dogen/cli/__init__.py` docstring ("stay thin, no business logic") | header-only |
| `docs/conf.py` | config (Sphinx) | config | none — RESEARCH "Minimal docs/conf.py" | header-only |
| `docs/<sphinx_target>.md` | content (drafted MyST) | file-I/O output | `README.md` + `README.md.license` sidecar | sidecar-analog (D-44 license) |
| `.readthedocs.yaml` | config | config | none — RESEARCH "Minimal .readthedocs.yaml"; header via inline `#` | header-only |
| `pyproject.toml` (MODIFY) | config | config | `pyproject.toml` (existing) | exact (extend in place) |
| `.github/workflows/ci.yml` (MODIFY) | config (CI) | config | `.github/workflows/ci.yml` (existing) | exact (extend in place) |
| `.pre-commit-config.yaml` (MODIFY) | config | config | `.pre-commit-config.yaml` (existing) | exact (extend in place) |
| `tests/test_*.py` (NEW) | test | request-response | `tests/test_smoke.py`, `tests/test_seam.py` | exact |
| import-linter contract | config | config | `scripts/seam_check.py` + its pyproject/pre-commit wiring | role-match (declarative replaces AST) |

---

## Shared Patterns

These apply to nearly every file in the phase and are the highest-value carry-overs. Plans should reference them once and reuse.

### Pattern S1 — REUSE/SPDX header (EVERY new source/config file)

**Source:** `src/dogen/__init__.py` lines 1-16 (identical block in every `.py`, the CI `ci.yml`, and `.pre-commit-config.yaml`). Canonical generator: `.reuse/templates/canonical.jinja2`. Binding spec: coding-guide.md §7.
**Apply to:** all new `.py`, `docs/conf.py`, `.readthedocs.yaml` (use `#` comment form). The full notice block, not a bare SPDX line.

```python
# This file is part of dogen, an agentic documentation-drafting framework.
#
# SPDX-FileCopyrightText: 2026 Canonical Ltd.
# SPDX-License-Identifier: GPL-3.0-only
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3, as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program. If not, see <http://www.gnu.org/licenses/>.
```

**Generate it, don't hand-type it:** `uvx reuse annotate --template canonical --copyright "Canonical Ltd." --license GPL-3.0-only --year 2026 <file>` reproduces this block byte-for-byte (template comment asserts byte-for-byte parity with §7).

### Pattern S2 — Drafted-content header via `.license` SIDECAR (D-44)

**Source:** `README.md` + `README.md.license` (sidecar carries the full notice block; the `.md` body stays clean). Identical pattern: `CONTRIBUTING.md.license`, `.gitignore.license`, `uv.lock.license`.
**Apply to:** the drafted `docs/<sphinx_target>.md`. Content prose must NOT carry an inline SPDX header (it would pollute the published page and be misparsed by REUSE). Use a `.license` sidecar instead. **License = the D-44 decision (lean CC-BY-SA-4.0; reconcile the `licensing.md` CC-BY-NC-SA-4.0 inconsistency at planning).** A new `LICENSES/CC-BY-SA-4.0.txt` must be added alongside the existing `LICENSES/GPL-3.0-only.txt`.

### Pattern S3 — Module docstring (NumPy convention, ruff D enforced)

**Source:** every Phase-1 `__init__.py` (e.g. `core/__init__.py` lines 18-24) — a docstring directly after the header, stating the module's responsibility AND the invariant it protects (e.g. "carries zero vendor imports"). Public functions document params/returns/raises (see `scripts/seam_check.py` `find_violations` docstring, lines 83-95).
**Apply to:** every new public module, class, function (coding-guide §2: `ruff D`, numpy convention). Per-file ignore for tests already configured in `pyproject.toml` line 44.

### Pattern S4 — Single-source-of-truth gate (script ↔ pytest ↔ CI ↔ pre-commit)

**Source:** the seam guardrail wired four ways with zero logic duplication:
- `scripts/seam_check.py` `main() -> int` (the one implementation; returns `0/1/2`),
- `tests/test_seam.py` lines 23-34 imports `seam_check` via `sys.path.insert(...)` and asserts `seam_check.main() == 0`,
- `.github/workflows/ci.yml` line 59-60 runs `uv run python scripts/seam_check.py`,
- `.pre-commit-config.yaml` lines 34-40 `local` hook `entry: python scripts/seam_check.py`.

```python
# tests/test_seam.py:20-34 — single-source pattern
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import seam_check  # noqa: E402

def test_no_vendor_imports_outside_adapter() -> None:
    assert seam_check.main() == 0
```

**Apply to:** the import-linter seam gate (D-29) and the docs-build/loop-smoke gates (D-24/D-43) — wire each gate once and reference it from CI + pre-commit + (where sensible) a test, never duplicating the logic. **Confirm at planning (D-29 open question):** keep `scripts/seam_check.py` AST check as belt-and-braces alongside import-linter (RESEARCH Pitfall 4 recommends keeping it).

### Pattern S5 — Seam-import discipline (the architecture invariant)

**Source:** coding-guide.md §6 + `adapters/copilot/__init__.py` docstring (lines 18-27, "the single location where `copilot` ... may be imported") + `scripts/seam_check.py` `BANNED_ROOTS = {"copilot", "github_copilot_sdk"}` (line 34) and `ADAPTER_DIR` exemption (line 36, 126-127).
**Apply to:** the import-linter forbidden contract must extend the banned set to `logfire` and `opentelemetry.sdk` (RESEARCH Pitfall 4): `core/*` may not import `copilot`, `logfire`, `opentelemetry.sdk`, or `adapters.*`. `core/observability.py` imports only `opentelemetry` (the *API*), never `opentelemetry.sdk` or `logfire`. The ONLY `logfire` import site is `obs/logfire_backend.py`; the ONLY `copilot` import site is `adapters/copilot/`.

---

## Pattern Assignments (per file)

### `src/dogen/core/models.py` (model, Pydantic v2)

**Analog:** `core/__init__.py` (header S1 + docstring S3). No model analog exists — shape from RESEARCH D-34/35/36/38 and coding-guide §2 "use real data structures".
**Core pattern (from RESEARCH, no in-repo analog):** Pydantic v2 `BaseModel`s for `Unit` (front-matter), `Steering`, `Generation`, `ReviewerEdit`, `Verification`, `Provenance`, `Progress`, plus `Intent`/`Audience`/`ProgressState` as `enum.Enum`, and a `DraftResult` domain type. Every machine-readable model carries `schema_version: int = 0` (D-34). `Intent = reference|tutorial|how-to|explanation`; `effort` enum MUST include `xhigh` (RESEARCH verified `reasoning_effort` Literal). `ProgressState = pending → sourced → drafted → reviewed → committed` but **no code path sets `committed`** (D-38, Pitfall 9). Keep `sources` (human-pointed) and `context_origins` (agent-read) as two distinct fields (D-37). **Zero vendor imports** (S5).
**Header:** S1. **Docstrings:** S3. **Functions ≤60 lines** (coding-guide §1.3).

### `src/dogen/core/ports.py` (port, Protocol)

**Analog:** `core/__init__.py` docstring already promises "Protocol ports it defines". RESEARCH Pattern 1.
**Core pattern:** `typing.Protocol` classes shaped by **domain verbs** (coding-guide §6, Anti-Pattern 2) — `DraftingProvider` (`async def draft_unit(*, intent, audience, steering, sources) -> DraftResult`), `SourceLookup`, `PlanningStore`. **Async** ports (RESEARCH Pitfall 2 — the SDK is async; a sync port would force `asyncio.run` in the adapter). No `copilot`/SDK types in any signature (S5).

### `src/dogen/core/orchestrator.py` (service, async use-case)

**Analog:** none (greenfield). Shape from RESEARCH "Architectural Responsibility Map" + Pattern 3 + the system diagram.
**Core pattern:** the one drafting use-case. Opens an OTel span (`tracer.start_as_current_span("dogen.draft")`), mints `run_id = format(span.get_span_context().trace_id, "032x")` (OBS-03/D-22), enforces the **HITL gate** (refuse if `provenance.steering` absent → clear message + nonzero exit, D-40/HITL-01), selects provider by domain choice (D-25), drives `await provider.draft_unit(...)`, hands the `DraftResult` to `PlanningStore` for the `.dogen/` + `docs/` writes, and auto-advances progress `pending→sourced→drafted` (never `committed`). Imports only `opentelemetry` API + `core` ports (S5).

### `src/dogen/core/observability.py` (utility, OTel API)

**Analog:** none — RESEARCH Pattern 3.
**Core pattern:** `from opentelemetry import trace; tracer = trace.get_tracer("dogen")` and small span/attribute helpers. **No `logfire`, no `opentelemetry.sdk` import here** (S5 / Pitfall 4) — that keeps OBS-01 (survives backend swap) true.

### `src/dogen/adapters/copilot/provider.py` (adapter — sole SDK importer)

**Analog:** `adapters/copilot/__init__.py` docstring (the sanctioned import site). RESEARCH "VERIFIED Copilot SDK API".
**Core pattern (verified 1.0.2 API):** `async with CopilotClient() as client: async with await client.create_session(model=..., reasoning_effort=..., available_tools=READONLY, excluded_tools=DENY, working_directory=...) as session: final = await session.send_and_wait(prompt, timeout=...)`. `create_session` **is a coroutine — must be `await`ed**. Read draft from `assistant.message` event → `AssistantMessageData.content/.model/.output_tokens` (via `mapping.py`). Backend-unavailable handled (SKEL-05/D-27): call `get_status()`/`get_auth_status()`, catch `StopError` + `__aenter__` connection failures → clear message + nonzero exit, never a crash. Implements `core.ports.DraftingProvider`. **The only place `from copilot import ...` appears** (S5).

### `src/dogen/adapters/copilot/tools.py` (adapter config — bounded read-only)

**Analog:** none — RESEARCH Pattern 2.
**Core pattern:** `from copilot import ToolSet`; `READONLY = ToolSet().add_builtin(["grep","glob","view"])` (allowlist, D-28) and `DENY = ToolSet().add_builtin(["bash","str_replace_editor","create"])` (denylist). NOTE: names are source-qualified `builtin:<name>` via `add_builtin` — bare strings raise (Pitfall 1). Exact `glob`/`view` names = local-smoke confirmation (Assumption A1).

### `src/dogen/adapters/copilot/mapping.py` (adapter — anti-corruption)

**Analog:** none — RESEARCH "Code Examples / mapping.py".
**Core pattern:** translate `SessionEvent`/`AssistantMessageData` → domain `DraftResult` so SDK types never reach `core/` (Anti-Pattern 1, Pitfall 4). `to_draft_result(evt, run_id) -> DraftResult` reading `data.content/.model/.output_tokens`.

### `src/dogen/adapters/mock_provider.py` (adapter — deterministic double, D-23)

**Analog:** none — implements `core.ports.DraftingProvider` like `copilot/provider.py` but with **no SDK import**.
**Core pattern:** `async def draft_unit(...) -> DraftResult` returning a canned, deterministic `DraftResult` + synthetic provenance fields. This is the CI-runnable proof of the full loop AND the SEAM-03/D-26 second-provider swap evidence. Must be deterministic (coding-guide §4 — no wall-clock/network).

### `src/dogen/adapters/planning_fs.py` (adapter — PlanningStore, file-I/O)

**Analog:** none. Header S1; YAML I/O via PyYAML (installed) for machine-written `provenance.yaml`/`progress.yaml`; consider `ruamel.yaml` only if the tool rewrites human-edited `unit.md` (RESEARCH A4 — decide at planning).
**Core pattern:** implements `core.ports.PlanningStore`; reads/writes the per-unit `.dogen/units/<id>/` tree (`unit.md` front-matter + body, `provenance.yaml`, `progress.yaml`) and writes the drafted MyST to `docs/<sphinx_target>.md`. **Never writes `.planning/`** (D-30). A small tested front-matter splitter (RESEARCH "Don't Hand-Roll") — not a regex.

### `src/dogen/adapters/git_identity.py` (adapter — host I/O)

**Analog:** none. coding-guide §5 (shell allowlist discipline).
**Core pattern:** reads `git config user.name` / `user.email` (D-41) behind a tiny adapter so shell I/O stays out of `core/`. Explicit allowlisted commands only — never arbitrary shell.

### `src/dogen/obs/logfire_backend.py` (config — composition root)

**Analog:** none — RESEARCH Pattern 3.
**Core pattern:** `import logfire; logfire.configure(send_to_logfire=False)` (D-21, local mode). **The ONLY `logfire` import in the codebase** (S5); wired from the CLI composition root, not from `core/`.

### `src/dogen/cli/main.py` (controller — Typer, thin)

**Analog:** `cli/__init__.py` docstring ("stay thin, holding no business logic, delegating into `dogen.core`").
**Core pattern:** Typer app with four thin subcommands (D-42): `unit new <id>`, `steer <id>`, `draft <id>`, `review <id> --note`. Each parses args, calls `asyncio.run(orchestrator....)` at the boundary (RESEARCH Pitfall 2 — the single event-loop entry), surfaces the HITL-refusal message + exit code from the core, reports written file paths at the end. No business logic in the CLI (coding-guide §6). A `[project.scripts]` console entry + `typer` dep land in `pyproject.toml`.

### `docs/conf.py` (config — Sphinx)

**Analog:** none — RESEARCH "Minimal docs/conf.py". Header S1 (`#` form).
**Core pattern:** `extensions = ["myst_parser"]`, `myst_enable_extensions = ["colon_fence"]`, `source_suffix = {".md": "markdown", ".rst": "restructuredtext"}` (D-43). Missing `myst_parser` → the build silently doesn't parse MyST (Pitfall 6) — it must be present.

### `docs/<sphinx_target>.md` (content — drafted MyST)

**Analog:** `README.md` + `README.md.license` sidecar (S2).
**Core pattern:** MyST page, referenced from a `toctree` (else `-W` fails, Pitfall 6). Carries NO inline SPDX header — license via `.license` sidecar (S2 / D-44). First unit = a reference/explanation page about dogen (D-32).

### `.readthedocs.yaml` (config)

**Analog:** none — RESEARCH "Minimal .readthedocs.yaml". Header S1 (`#` form).
**Core pattern:** `version: 2`, `build.tools.python: "3.12"`, `sphinx.configuration: docs/conf.py`, `sphinx.fail_on_warning: true`, install `.[docs]`.

### `pyproject.toml` (MODIFY — exact analog, extend in place)

**Analog:** the existing `pyproject.toml` (read fully). **Extend, do not rewrite.** Keep the header (lines 1-16), `[build-system]`, `[project]` license block, `[tool.ruff.lint]` select set, numpy pydocstyle, the `tests/**` per-file ignore (line 44), `[tool.ty.environment]` (note `extra-paths = ["scripts"]` line 51), `[tool.pytest.ini_options]`.
**Additions:** runtime deps (`github-copilot-sdk==1.0.2`, `typer`, `pydantic>=2`, `opentelemetry-api`, `logfire`) in `[project] dependencies`; `[project.optional-dependencies] docs = ["sphinx==9.1.0","myst-parser==5.1.0","furo"]`; `import-linter` into the existing `dev` group (line 34); a `[project.scripts] dogen = "dogen.cli.main:app"` entry; an `[tool.importlinter]` contract section. Pin exactly per coding-guide §2 ("pin what you import").

### `.github/workflows/ci.yml` (MODIFY — exact analog, extend in place)

**Analog:** the existing `ci.yml` (read fully). **Extend the `gates` job**, preserving: SHA-pinned first-party actions (lines 37-42), `permissions: contents: read`, `uv sync --frozen` (line 44), and the **gate order that mirrors pre-commit + seam_check** (line 45 comment).
**Additions:** an import-linter step (next to/after the seam-check step, line 59); a **docs-build job** `uv run --extra docs sphinx-build -W -b html docs docs/_build` (Python 3.12 only — Sphinx 9.1 floor); ensure `pytest` runs the loop via `--provider mock` (D-24 — **no SDK/Copilot token in CI**). The real-SDK smoke test stays OUT of CI (D-24).

### `.pre-commit-config.yaml` (MODIFY — exact analog, extend in place)

**Analog:** the existing `.pre-commit-config.yaml` (read fully). **Mirror the new CI gates** here (the file's own header comment, line 18, states it mirrors CI). Keep the `reuse` (v6.2.0), `ruff`/`ruff-format` (v0.15.18), and the `local` seam-check + `ty` hooks. Add a `local` import-linter hook following the exact `local`-hook shape used for `seam-check`/`ty` (lines 34-48): `language: system`, `pass_filenames: false`.

### `tests/test_*.py` (NEW — exact analog)

**Analog:** `tests/test_smoke.py` (header S1; module docstring; `importlib` behaviour assertions) and `tests/test_seam.py` (single-source gate invocation).
**Core pattern:** `pytest` + `pytest-asyncio` (async loop). Per coding-guide §4: **mock only at the true boundary** — the `DraftingProvider` port (use `MockDraftingProvider`) and `git_identity` host I/O; use real objects in the core. Drive `unit new → steer → draft → review` end-to-end, asserting the four files appear with correct schema, the HITL gate refuses without steering (nonzero exit), and `progress.yaml` never reaches `committed`. Deterministic, order-independent. Tests inherit the `tests/**` ruff ignores (`D`, `ANN`, `PLR2004`).

### import-linter contract (NEW — role-match for `seam_check.py`)

**Analog:** `scripts/seam_check.py` (`BANNED_ROOTS`, adapter exemption) + its four-way wiring (S4). import-linter is the **declarative** form of the same invariant (D-29).
**Core pattern:** a forbidden/layered contract in `[tool.importlinter]`: `core` forbidden from importing `copilot`, `github_copilot_sdk`, `logfire`, `opentelemetry.sdk`, and `adapters.*`. Wire into CI + pre-commit (S4). **Open question (D-29):** keep the AST `seam_check.py` as belt-and-braces (RESEARCH Pitfall 4 recommends yes) — confirm at planning.

---

## No Analog Found

These have **no role+data-flow analog** in the codebase (it is a greenfield phase filling empty stubs). They DO inherit the shared header/docstring/test/seam patterns (S1–S5); their **core logic** must come from RESEARCH.md (verified SDK API) + ARCHITECTURE.md patterns, as cited per file above.

| File | Role | Data Flow | Pattern Source (no in-repo analog) |
|------|------|-----------|-----------------------------------|
| `core/orchestrator.py` | service | async request-response | RESEARCH Responsibility Map + Pattern 3 |
| `core/observability.py` | utility | event-driven (OTel) | RESEARCH Pattern 3 |
| `adapters/copilot/provider.py` | adapter | async streaming | RESEARCH "VERIFIED Copilot SDK API" |
| `adapters/copilot/tools.py` | config | config | RESEARCH Pattern 2 |
| `adapters/copilot/mapping.py` | adapter | transform | RESEARCH "Code Examples" |
| `adapters/mock_provider.py` | adapter | async request-response | D-23 (implements `ports.DraftingProvider`) |
| `adapters/planning_fs.py` | adapter | file-I/O | D-31/33; RESEARCH "Don't Hand-Roll" |
| `adapters/git_identity.py` | adapter | shell I/O | D-41; coding-guide §5 |
| `obs/logfire_backend.py` | config | config | RESEARCH Pattern 3 |
| `docs/conf.py` | config | config | RESEARCH "Minimal docs/conf.py" |
| `.readthedocs.yaml` | config | config | RESEARCH "Minimal .readthedocs.yaml" |

---

## Metadata

**Analog search scope:** `src/dogen/**`, `tests/**`, `scripts/**`, `.github/workflows/`, `.pre-commit-config.yaml`, `pyproject.toml`, `REUSE.toml`, `.reuse/templates/`, root OSS-hygiene `.license` sidecars.
**Files scanned:** 7 source stubs, 2 tests, 1 script, 1 CI workflow, 1 pre-commit config, 1 pyproject, 1 REUSE.toml, 1 jinja2 template, README.md.license sidecar.
**Key finding:** zero existing files with domain logic — Phase 1 is pure scaffold. The durable, copy-from patterns are cross-cutting (S1–S5), not per-role. Per-file core logic is sourced from RESEARCH.md's verified `github-copilot-sdk==1.0.2` API and ARCHITECTURE.md patterns.
**Pattern extraction date:** 2026-06-19
```
