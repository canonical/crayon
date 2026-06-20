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
>
> **Re-audit 2026-06-20 (post-`9949e86`):** nine code-changing commits (`f3a1dba` BL-01, `4197a54` WR-01, `730dd54` WR-02, `e37a828` WR-03, `234d6d2` WR-04, `892efae` WR-05, `ee86206` WR-06, `5ff604b` IN-02, `d343155` IN-03, `90fbf48` IN-01) landed after the original audit, touching every cited file. Every mitigation was re-resolved to CURRENT file:line evidence against the working tree (the table below is refreshed; prior line numbers were stale). **All nine commits reinforce, none weaken, the declared mitigations.** Verdict unchanged: 18/18 closed, 0 open.

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
| T-02.1-01 | Tampering | `FilesystemPlanningStore` path construction from `<unit-id>` | mitigate | Reject unsafe `unit_id` (separators/`..`/abs) `planning_fs.py:315-331`; positive root containment `planning_fs.py:350-373`; `.planning/` guard `planning_fs.py:375-393`; positive `docs/` containment on draft write `planning_fs.py:197-205`; schema-level `sphinx_target` containment validator `models.py:165-192` | closed |
| T-02.1-02 | Elevation of Privilege | `git_identity` subprocess | mitigate | Exact-vector allowlist (no `shell=`, no interpolation) `git_identity.py:34-37`; list-form `subprocess.run(check=False)` `git_identity.py:60-61`; IN-02 explicit `git config --get` read form `git_identity.py:31-37` | closed |
| T-02.1-03 | Tampering | seam erosion (forbidden imports in `core`) | mitigate | import-linter forbidden contract bans `copilot/github_copilot_sdk/logfire/opentelemetry.sdk/dogen.adapters` `pyproject.toml:94-110`; AST belt-and-braces `scripts/seam_check.py:34` (`BANNED_ROOTS`); CI runs both `ci.yml:59-65` | closed |
| T-02.1-SC | Tampering | uv/pip supply-chain installs | mitigate | `github-copilot-sdk==1.0.2` exact pin + version floors `pyproject.toml:32-38`; frozen CI install `ci.yml:43-44,83-84` (`uv sync --frozen`) | closed |
| T-02.2-01 | Repudiation / Tampering | HITL steering gate (`provenance.steering`) | mitigate | Domain invariant: draft refuses (`SteeringRequiredError`, no side effects) without prior `steer` `orchestrator.py:147-195`; CLI surfaces nonzero exit `cli/main.py:221-223`; WR-03 audit record written before draft `orchestrator.py:236-247`; WR-04 re-steer refused unless `--re-steer` so `steering.at` cannot be pushed past `generations[0].at` `cli/main.py:157-167` | closed |
| T-02.2-02 | Tampering | progress lifecycle reaching `committed` | mitigate | No code path writes `ProgressState.committed`; auto-advance ladder excludes it `orchestrator.py:57-76,300-342`; review tops out at `reviewed` `cli/main.py:290-296`; WR-02 `Unit.status` reserved, not a live mirror `models.py:149-153,163` | closed |
| T-02.2-03 | Information Disclosure | secrets leaking into spans / Logfire / provenance | mitigate | Span attributes restricted to `unit_id/intent/provider/run_id` `observability.py:43-46,104-107`; Logfire `send_to_logfire=False` `logfire_backend.py:45`; BL-01 `context_origins/tools_used` come only from provider result, never fabricated `orchestrator.py:275-297` | closed |
| T-02.3-01 | Elevation of Privilege | the agent's toolset | mitigate | Read-only allowlist `grep/glob/view` + write/exec/network denylist, source-qualified via `add_builtin` `tools.py:45-63`; applied at the only session site `provider.py:169-176` (`available_tools=READONLY, excluded_tools=DENY`) | closed |
| T-02.3-02 | Tampering / Information Disclosure | prompt injection from agent-read source content | mitigate | Read-only toolset (cannot act outside drafting) `tools.py:45-63`; scope-bounding system message ("Draft only; never commit, push, or modify files") `provider.py:279-283`; human review before commit `cli/main.py:240-296`; BL-01 `context_origins` recorded verbatim from provider `orchestrator.py:275-297` | closed |
| T-02.3-03 | Denial of Service / robustness | backend unavailable; CLI transport break (#1606) | mitigate | `get_status`/`get_auth_status` pre-flight → `BackendUnavailableError` `provider.py:185-207`; `StopError`/connection handling `provider.py:136-145`; WR-01 CLI classifies by name (mock path never imports the SDK adapter) `cli/main.py:227-236` | closed |
| T-02.3-04 | Information Disclosure | Copilot auth token | mitigate | No token/secret/api-key read or written in `src/`+`scripts/` (grep: every `token` hit is `output_tokens` count or no-secret prose); token never reaches provenance/spans; live path is the manual smoke only `smoke_draft.py:18-39` (CI uses `--provider mock`) | closed |
| T-02.3-SC | Tampering | Copilot CLI runtime auto-updating | mitigate | SDK `==1.0.2` pin `pyproject.toml:33`; bundled CLI `1.0.64-0` recorded as bump-gate `tools.py:26-27`, re-read live by the smoke harness `smoke_draft.py:179-182` | closed |
| T-02.4-01 | Information Disclosure | provenance/model metadata leaking into published `docs/*.md` | mitigate | Draft-write emits prose only to `docs/` `planning_fs.py:180-212`; provenance/progress stay under `.dogen/` `orchestrator.py:243-246`; grep of `docs/*.md` finds no metadata *values* (no run_id/model_version/timestamps) — only descriptive prose naming the fields | closed |
| T-02.4-02 | Tampering | wrong/inconsistent docs license id | mitigate | Docs license resolved CC-BY-SA-4.0 `docs/cli-reference.md.license`, `LICENSES/CC-BY-SA-4.0.txt`; `.license` sidecars (no inline SPDX in prose); reuse-lint gated `ci.yml:46-47` | closed |
| T-02.4-03 | Tampering | build output (`docs/_build`) entering tracked tree | mitigate | `docs/_build/` gitignored so generated HTML is never source-scanned `.gitignore:12-15` | closed |
| T-02.4-05 | Tampering | `.dogen/**` REUSE.toml glob widening | mitigate | Glob scoped to `.dogen/**` only, `precedence = "aggregate"`, `GPL-3.0-only` `REUSE.toml:36-40`; existing `.planning/**`/`.claude/**` entries untouched `REUSE.toml:18-29`; reuse-lint gated | closed |
| T-02.2-04 | Spoofing | recorded author identity | accept | Author is local-git-config audit metadata (D-41), not an authn claim; see Accepted Risks Log | closed |
| T-02.4-04 | Information Disclosure | committing the `.dogen/**` audit surface | accept | Intended AC5 design (D-24); committed surface re-verified to hold no secrets (IN-01 `model_version: mock-1`); see Accepted Risks Log | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-02-01 | T-02.2-04 | Author/reviewer identity is captured from local `git config` (D-41) as **audit metadata for the AC5 trail**, not an authentication or authorization claim — trusted-local-operator context, not cryptographically enforced. **Re-confirmed against current code:** `git_identity.py:64-89` reads `user.name`/`user.email` (IN-02: explicit `--get` read form); stamped onto `Steering.author` (`cli/main.py:177-179`) / `ReviewerEdit.reviewer` (`cli/main.py:282-284`); no code path treats this value as an authn/authz gate. Rationale holds. | Operator (gsd-secure-phase) | 2026-06-20 |
| AR-02-02 | T-02.4-04 | The committed `.dogen/**` audit trail living in git history is the intended AC5 design (D-24); provenance records only non-sensitive domain metadata, never secrets (enforced by T-02.2-03), so committing it is a recorded, accepted internal-observability disclosure. `.planning/` stays excluded (D-30). **Re-confirmed against the actual committed surface (post-IN-01):** `.dogen/units/cli-reference/{provenance.yaml,progress.yaml,unit.md}` contain `unit_id`, steering `{author,at,intent,audience}`, generation `model=mock-model/model_version=mock-1/effort/tooling_version/sdk/run_id/at`, `context_origins: []`, `tools_used: []` (BL-01 honest-empty), reviewer note, and timestamps — **no token, key, or secret**; `progress.state` tops out at `reviewed`, never `committed`. IN-01's `model_version: mock-1` fix is reflected. Rationale holds. | Operator (gsd-secure-phase) | 2026-06-20 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-20 | 18 | 18 | 0 | gsd-security-auditor (opus) |
| 2026-06-20 (re-audit, post-`9949e86`) | 18 | 18 | 0 | gsd-security-auditor (opus) |

**Audit notes:** Register authored at plan time (`<threat_model>` block in all four PLANs) → verify-mitigations mode, no new-threat scan. 16 `mitigate` threats confirmed present in implementation + tests with file:line evidence; 2 `accept` threats confirmed against code (and, for T-02.4-04, against the actual committed `.dogen/` surface). No unregistered flags: both self-reported "Threat surface scan" sections (`02-02-SUMMARY.md`, `02-03-SUMMARY.md`) report no new surface; no SUMMARY emitted a `## Threat Flags` section.

**Re-audit notes (2026-06-20, working tree @ `d0deabe`):** Nine code-changing commits landed after the first audit (`9949e86`), touching every file the register cites: `f3a1dba` (BL-01), `4197a54` (WR-01), `730dd54` (WR-02), `e37a828` (WR-03), `234d6d2` (WR-04), `892efae` (WR-05), `ee86206` (WR-06), `5ff604b` (IN-02), `d343155` (IN-03), `90fbf48` (IN-01). Every mitigation was re-resolved to CURRENT file:line evidence (prior line numbers were stale and are now refreshed in the register above). The post-audit commits **reinforce** the declared mitigations and open no new gaps: WR-03 makes the audit record durable before the draft and writes YAML atomically (strengthens T-02.2-01); WR-04 refuses a silent re-steer that would invert the `steering.at < generations[0].at` ordering (strengthens T-02.2-01); WR-02 marks `Unit.status` reserved so it is not mistaken for the live lifecycle (clarifies T-02.2-02); BL-01/IN-03 stop fabricating `context_origins`/`tools_used` and record provider-reported effort (strengthens T-02.2-03 / the audit honesty behind T-02.4-04); WR-01 classifies `BackendUnavailableError` by name so the mock path never imports the SDK adapter (strengthens the T-02.3-03 seam); WR-05 coerces `None` content so the mapping degrades instead of crashing (robustness, T-02.3-03); WR-06 gives an unknown `--provider` a clean exit-2 (UX, no security regression); IN-02 uses the explicit `git config --get` read form (tightens T-02.1-02); IN-01 corrected the committed dogfood `model_version` to `mock-1` (re-verified in `.dogen/`, AR-02-02). No mitigation was found absent or weakened. Verdict unchanged: 18/18 closed, 0 open.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-20
