---
phase: 02
slug: walking-skeleton-planning-schema-provable-hitl-observability
status: verified
threats_open: 0
asvs_level: 1
created: 2026-06-20
---

# Phase 02 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
>
> **Verdict: SECURED** — 18/18 threats resolved (16 mitigations verified in code + tests; 2 accepted risks confirmed against the actual committed surface). Register authored at plan time; auditor verified declared mitigations, no blind scan for new threats. Implementation files were read-only throughout.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| operator → CLI | Operator-supplied `<unit-id>` and `--intent`/`--audience`/`--note` strings cross into filesystem path construction and the recorded audit surface | Untrusted operator input (path components, free text) |
| CLI/adapter → filesystem | The store writes under the repo root; must never escape into `.planning/` or outside `.dogen/`/`docs/` roots | Drafted prose + provenance YAML |
| adapter → host (git) | `git_identity` shells `git config`; an unbounded shell here is a host-level risk | git-config author/email (local, trusted operator) |
| orchestrator → provenance | The HITL gate + provenance record are the integrity surface AC5 audits depend on | Steering events, generation records, run_id |
| core → observability backend | Spans/run_id must not carry secrets into traces/logs | Domain metadata only (unit_id, intent, provider, run_id) |
| dogen → Copilot SDK/CLI | The adapter drives an external subprocess over JSON-RPC; the bounded toolset is the security boundary | Bounded read-only toolset; agent-read source content (untrusted) |
| agent → source files | The agent reads operator-pointed source content that flows into the draft (prompt-injection vector) | Untrusted source content |
| drafted content → published docs | Provenance/model metadata must not leak into published `.md` (no public AI disclaimer) | Prose only |
| licensing system-of-record → reuse lint | A wrong/inconsistent SPDX id mis-licenses published prose | SPDX license identifiers |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-02.1-01 | Tampering | `FilesystemPlanningStore` path construction from `<unit-id>` | mitigate | Reject `unit_id` with separators/`..`; positive containment to `.dogen/units/`; `.planning/` guard — `planning_fs.py:280-297,316-359,195-205` + `models.py:159-186`; tests `test_planning_fs.py:70,110,144` | closed |
| T-02.1-02 | Elevation of Privilege | `git_identity` subprocess | mitigate | Exact-vector allowlist, list-form `subprocess.run` (no `shell=`, no interpolation) — `git_identity.py:31-34,43-58,80-81`; test `test_planning_fs.py:191-205` | closed |
| T-02.1-03 | Tampering | seam erosion (forbidden imports in `core`) | mitigate | import-linter forbidden contract + AST belt-and-braces — `pyproject.toml:100-110`, `scripts/seam_check.py`; tests `test_seam_importlinter.py:54`, `test_observability_correlation.py:88`; CI `ci.yml:59-65` | closed |
| T-02.1-SC | Tampering | uv/pip supply-chain installs | mitigate | `github-copilot-sdk==1.0.2` exact pin + floors `pyproject.toml:32-38`; frozen CI install `ci.yml:43-44` (`uv sync --frozen`) | closed |
| T-02.2-01 | Repudiation / Tampering | HITL steering gate (`provenance.steering`) | mitigate | Domain invariant: draft refuses (nonzero exit, no side effects) without prior recorded `steer`; steering provably precedes generation — `orchestrator.py:147-195`, `cli/main.py:182-184`; tests `test_orchestrator_hitl.py:131,224`, `test_loop_mock_e2e.py:105` | closed |
| T-02.2-02 | Tampering | progress lifecycle reaching `committed` | mitigate | No code path writes `ProgressState.committed`; auto-advance ladder excludes it; AST scan test fails if reintroduced — `orchestrator.py:57-76`; test `test_orchestrator_hitl.py:213-221` | closed |
| T-02.2-03 | Information Disclosure | secrets leaking into spans / Logfire / provenance | mitigate | Span attributes restricted to `unit_id/intent/provider/run_id`; Logfire `send_to_logfire=False`; no token/env as attribute — `observability.py:42-47,78-107`, `logfire_backend.py:45`; tests `test_observability_correlation.py:88` | closed |
| T-02.3-01 | Elevation of Privilege | the agent's toolset | mitigate | Read-only allowlist (`grep`/`glob`/`view`) + write/exec/network denylist, applied at the only session site — `tools.py:45,48-57`, `provider.py:169-176`; test `test_copilot_mapping.py:92-118` | closed |
| T-02.3-02 | Tampering / Information Disclosure | prompt injection from agent-read source content | mitigate | Read-only toolset (cannot act outside drafting) + scope-bounding system message + human review before commit + `context_origins` recorded — `provider.py:259-280`, `orchestrator.py:272`, `cli/main.py:213-269` | closed |
| T-02.3-03 | Denial of Service / robustness | backend unavailable; CLI transport break (#1606) | mitigate | `get_status`/`get_auth_status` pre-flight + `StopError`/connection handling → `BackendUnavailableError` (clear message, nonzero exit, no crash) — `provider.py:136-145,182-203`, `cli/main.py:185-187`; tests `test_copilot_backend_unavailable.py:106-131` | closed |
| T-02.3-04 | Information Disclosure | Copilot auth token | mitigate | No token read/written in `src/`+`scripts/` (grep); token never reaches provenance/spans; CI uses `--provider mock` — `test_loop_mock_e2e.py:157-169`; live path is the manual smoke only `smoke_draft.py` | closed |
| T-02.3-SC | Tampering | Copilot CLI runtime auto-updating | mitigate | SDK `==1.0.2` pin; bundled CLI `1.0.64-0` recorded as bump-gate, re-read live by the smoke harness — `provider.py:32`, `tools.py:26-27`, `smoke_draft.py:179-182` | closed |
| T-02.4-01 | Information Disclosure | provenance/model metadata leaking into published `docs/*.md` | mitigate | Draft-write emits prose only; provenance stays in `.dogen/` — `planning_fs.py:178-208`, `orchestrator.py:236-238`; committed `docs/cli-reference.md` carries no metadata values | closed |
| T-02.4-02 | Tampering | wrong/inconsistent docs license id | mitigate | Docs license resolved CC-BY-SA-4.0; `LICENSES/CC-BY-SA-4.0.txt` + `.license` sidecars; reuse-lint gated in CI — `ci.yml:46-47` | closed |
| T-02.4-03 | Tampering | build output (`docs/_build`) entering tracked tree | mitigate | `docs/_build/` gitignored so generated HTML is never source-scanned — `.gitignore:12-13` | closed |
| T-02.4-05 | Tampering | `.dogen/**` REUSE.toml glob widening | mitigate | Glob scoped to `.dogen/**` only, `precedence = "aggregate"`, `GPL-3.0-only`; `.planning/**`/`.claude/**` untouched; reuse-lint gated — `REUSE.toml:36-40` | closed |
| T-02.2-04 | Spoofing | recorded author identity | accept | Author is local-git-config audit metadata (D-41), not an authn claim; see Accepted Risks Log | closed |
| T-02.4-04 | Information Disclosure | committing the `.dogen/**` audit surface | accept | Intended AC5 design (D-24); committed surface verified to hold no secrets; see Accepted Risks Log | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-02-01 | T-02.2-04 | Author/reviewer identity is captured from local `git config` (D-41) as **audit metadata for the AC5 trail**, not an authentication or authorization claim — trusted-local-operator context, not cryptographically enforced. **Confirmed against code:** `git_identity.py:61-86` reads `user.name`/`user.email`; stamped onto `Steering.author`/`ReviewerEdit.reviewer` (`cli/main.py:142-144,255-257`); no code path treats this value as an authn/authz gate. Rationale holds. | Operator (gsd-secure-phase) | 2026-06-20 |
| AR-02-02 | T-02.4-04 | The committed `.dogen/**` audit trail living in git history is the intended AC5 design (D-24); provenance records only non-sensitive domain metadata, never secrets (enforced by T-02.2-03), so committing it is a recorded, accepted internal-observability disclosure. `.planning/` stays excluded (D-30). **Confirmed against the actual committed surface:** `.dogen/units/cli-reference/{provenance.yaml,progress.yaml,unit.md}` contain `unit_id`, steering `{author,at,intent,audience}`, generation `model/version/effort/tooling_version/sdk/run_id/at`, reviewer note, and timestamps — **no token, key, or secret**. Rationale holds. | Operator (gsd-secure-phase) | 2026-06-20 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-20 | 18 | 18 | 0 | gsd-security-auditor (opus) |

**Audit notes:** Register authored at plan time (`<threat_model>` block in all four PLANs) → verify-mitigations mode, no new-threat scan. 16 `mitigate` threats confirmed present in implementation + tests with file:line evidence; 2 `accept` threats confirmed against code (and, for T-02.4-04, against the actual committed `.dogen/` surface). No unregistered flags: both self-reported "Threat surface scan" sections (`02-02-SUMMARY.md`, `02-03-SUMMARY.md`) report no new surface; no SUMMARY emitted a `## Threat Flags` section.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-20
