---
phase: 04
slug: honest-observed-provenance
status: verified
threats_open: 0
asvs_level: 1
created: 2026-06-22
---

# Phase 04 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

This phase introduces **no new tool, permission, write/exec/network, or external
input surface** — it only *observes* tool-call events already produced inside the
bounded READONLY session (`grep`/`glob`/`view`; write/exec/network were already
DENY'd in Phase 3). The register was authored at plan time in `04-01-PLAN.md`;
all dispositions are verified closed below. ASVS L1, block on `high`.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Copilot CLI runtime → adapter | Already-executed tool-call events (`TOOL_EXECUTION_START.data.arguments`, typed `Any`) cross from the SDK/CLI into `mapping.py`. The arguments are untrusted strings owned by the CLI runtime. | Untrusted CLI dict (`arguments`), tool names |
| adapter → core/ | Only plain `list[str]` (`context_origins`, `tools_used`) crosses into `core/` via `DraftResult` — no SDK shape (SEAM-01/03). | `tuple[list[str], list[str]]` — pure domain strings |
| core/ → provenance.yaml | Derived strings are serialised verbatim into the audit record (unchanged orchestrator path). | YAML-safe scalars (file paths, `builtin:<name>`) |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-04-01 | Tampering / DoS | `tool_events_to_provenance` reading `data.arguments` (`Any`, untrusted CLI dict) | mitigate | Defensive `getattr(data, "tool_name", "") or ""`, `isinstance(args, dict)` then `args.get("path")`, `isinstance(path, str) and path` before recording (omit-on-doubt, V5). Malformed/`None`-arg event degrades to honest-empty, never crashes the draft. Verified: `mapping.py:132–143`; `tests/test_copilot_provenance.py` green (14 passed). | closed |
| T-04-02 | Repudiation / integrity | The honest-empty contract (D-05/BL-01) — a fabricated or `sources`-copied origin would be a misleading audit record | mitigate | Lists fill ONLY from observed `TOOL_EXECUTION_START` evidence; never back-filled from `unit.sources` (orchestrator D-37 ban unchanged). Verified: `test_generation_does_not_fabricate_context_origins` + `test_draft_honest_empty_when_no_events` green. | closed |
| T-04-03 | Information Disclosure | Recorded `context_origins` reveals a path the human never pointed at | accept | Intended honesty — records what was *read*; path is bounded by the READONLY allowlist + `approve_all` scope set in Phase 3. No new disclosure surface; recorded as a plain YAML-safe scalar, never executed/interpreted. | closed |
| T-04-04 | Tampering (integrity) | A CLI version drift renaming `view`'s `path` arg key silently empties `context_origins` | mitigate | Centralised `_VIEW_PATH_KEY = "path"` named constant (`mapping.py:48`); fake-SDK unit test pins the contract; degrade to honest-empty (never fabricate). D-24 manual live run (UAT Test 1) **confirmed the real key** — `context_origins`/`tools_used` populated from live session events. | closed |
| T-04-05 | Tampering (architectural) | An SDK type (`SessionEvent`/`SessionEventType`/`ToolExecutionStartData`) crossing into `core/` | mitigate | Helper returns `tuple[list[str], list[str]]` only (`mapping.py:96–98`); import-linter forbidden contract + AST seam guard stay green. Verified: `tests/test_seam.py` + `tests/test_seam_importlinter.py` green. | closed |
| T-04-SC | Tampering (supply chain) | npm/pip/cargo installs | accept | No package install in this phase — `github-copilot-sdk==1.0.2` is already an adopted, pinned dependency (RESEARCH Package Legitimacy Audit: not applicable). No new dependency, no install task. | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-04-01 | T-04-03 | Recording the actual `view`-read path is the intended honesty behaviour (BL-01); paths are bounded by the Phase 3 READONLY allowlist and are inert YAML scalars (never executed). No disclosure surface beyond what the operator can already read in the repo. | Artem Konev | 2026-06-22 |
| AR-04-02 | T-04-SC | No dependency added this phase; the only SDK (`github-copilot-sdk==1.0.2`) was already adopted and pinned. Supply-chain threat is not applicable to this change. | Artem Konev | 2026-06-22 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-22 | 6 | 6 | 0 | gsd-secure-phase (orchestrator-verified, plan-time register) |

All six plan-time threats verified closed without spawning the auditor:
`threats_open: 0` with `register_authored_at_plan_time: true` (the short-circuit
path). Mitigations confirmed by direct code inspection (`mapping.py`) and the
security-bearing test suite (14 passed); D-24 live confirmation passed via UAT.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-22
