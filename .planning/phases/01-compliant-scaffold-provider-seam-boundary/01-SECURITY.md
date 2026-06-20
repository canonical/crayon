---
phase: 01
slug: compliant-scaffold-provider-seam-boundary
status: verified
threats_open: 0
asvs_level: 1
created: 2026-06-20
---
<!-- REUSE-IgnoreStart -->

# Phase 1 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Plan-time STRIDE register (4 plans) verified against the **current** working tree.

**Audit verdict:** SECURED after escalation ratification — 12 threats verified present in code,
3 escalations (controls superseded/contradicted by deliberate Phase-2 work) ratified as accepted
dispositions / Phase-2 handoffs by the human operator. `threats_open: 0`. ASVS Level 1, `block_on: high`,
no high-severity threats.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| upstream PyPI/SPDX → local repo | `reuse` fetches license text and runs as a dev tool | Public SPDX license text (no secrets) |
| dev-dep resolver (uv) → local env | uv resolves/locks ruff/ty/pytest/pre-commit/import-linter | Pinned, hashed dependency artifacts |
| package source tree → seam invariant | AST seam check protects the architecture boundary | Import graph (`copilot`/`github_copilot_sdk`) |
| external contributor → repo | CONTRIBUTING + CLA govern inbound code; top-level SECURITY.md governs vuln intake | Source contributions, vulnerability reports |
| GitHub Actions runner → repo | CI executes the gate suite with the default token | `GITHUB_TOKEN` (contents: read) |
| third-party GitHub Actions (uses:) → CI | external action code crosses into the runner | Pinned first-party actions only |
| developer edit → seam invariant | CI + pre-commit seam gate is the standing control | Import graph at commit/build time |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-01-01 | Tampering | reuse-fetched license text | accept | Canonical SPDX text via `reuse download`; verified by lint gate + grep; no execution of fetched content | closed |
| T-01-02 | Information Disclosure | header notice template | accept | `.reuse/templates/canonical.jinja2` is public policy text; no secrets | closed |
| T-01-SC | Tampering | uvx/reuse tool install | mitigate | `reuse` run via `uvx` (not a project dep); `ci.yml` + pre-commit `fsfe/reuse-tool` rev v6.2.0 version-matched; legitimacy-audited in RESEARCH | closed |
| T-02-01 | Tampering | dev dependencies (ruff/ty/pytest/pytest-asyncio/pre-commit) | mitigate | Pinned in committed `uv.lock` (D-18); dev group in `pyproject.toml`; legitimacy-audited | closed |
| T-02-02 | Tampering (arch invariant) | seam boundary (hidden vendor import) | mitigate | `scripts/seam_check.py` pure-stdlib AST (catches alias, submodule, `import_module` string-const); single-sourced by `tests/test_seam.py`; live planted import → exit 1, clean → exit 0 | closed |
| T-02-SC | Tampering | github-copilot-sdk supply chain | accept (Phase-2 handoff) | Phase-1 "no SDK dep" control **superseded** by Phase 2 (SDK now a pinned, hashed runtime dep). Ratified: re-mitigation owned by the Phase-2 threat model — see Escalation F1 | closed |
| T-02-03 | Tampering | build-time code execution | accept | hatchling backend, no build hooks/postinstall; Phase-1 tools have no postinstall scripts | closed |
| T-03-01 | Repudiation | inbound contributions | mitigate | `CONTRIBUTING.md` references the Canonical CLA + "License granted by Canonical Limited" variant (D-06) | closed |
| T-03-02 | Information Disclosure | SECURITY.md (top-level hygiene doc) | accept | Brief reporting policy (security@canonical.com); no secrets, no internal infra detail | closed |
| T-03-03 | Tampering | hygiene-file licensing gaps | mitigate | Per-file REUSE info intact (122/122, Missing=0, Bad=0). Standing whole-repo `reuse lint` gate currently RED on Phase-2 prose only — ratified as Phase-2 debt; see Escalations F2/F3 | closed |
| T-04-01 | Tampering / EoP | third-party GitHub Actions | mitigate | Only `actions/checkout` + `astral-sh/setup-uv`, SHA-pinned; no other `uses:` | closed |
| T-04-02 | Elevation of Privilege | workflow token scope | mitigate | Top-level least-privilege `permissions: contents: read`; no secrets referenced | closed |
| T-04-03 | Tampering (arch invariant) | seam-check bypass | mitigate | AST seam check on every CI build + pre-commit; D-10 SC4 demo captured. **Strengthened**: Phase-2 import-linter successor contract ("core stays vendor/adapter-free") verified KEPT live | closed |
| T-04-04 | Tampering | gate silencing (ty --exit-zero) | mitigate | Plain `uv run ty check`, no `--exit-zero`; documented beta fallback is `continue-on-error` + tracked issue, never a checker swap (D-14) | closed |
| T-04-SC | Tampering | dev-tool supply chain in CI | mitigate | `uv sync --frozen` installs only pinned `uv.lock`; `uvx reuse` resolves the same version pinned in pre-commit (v6.2.0) | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

Residual (register-acknowledged, accepted): dynamic string-constructed imports are out of scope for
the AST seam check — `import-linter` is the named Phase-2 successor (now present and verified live).

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-01-01 | T-01-01 | reuse-fetched canonical SPDX text; content verified by the lint gate, no execution | Operator | 2026-06-20 |
| AR-01-02 | T-01-02 | Notice block is public policy text; no secrets | Operator | 2026-06-20 |
| AR-01-03 | T-02-03 | hatchling build runs no untrusted code; Phase-1 tools have no postinstall scripts | Operator | 2026-06-20 |
| AR-01-04 | T-03-02 | Top-level SECURITY.md is a brief reporting policy; no secrets/internal infra | Operator | 2026-06-20 |
| AR-01-05 | T-02-SC (F1) | Phase-1 "SDK-free" control deliberately superseded by Phase 2; SDK is pinned+hashed; issue-#1606 re-mitigation handed off to the Phase-2 threat model | Operator | 2026-06-20 |
| AR-01-06 | T-03-03 (F2) | Meta-only `REUSE.toml` (`.planning/**`, `.claude/**`, `.dogen/**`, precedence aggregate) ratified as the accepted D-04 interpretation; per-file source headers still win | Operator | 2026-06-20 |
| AR-01-07 | T-01-SC / T-03-03 (F3) | Standing `reuse lint` RED only on Phase-2 planning prose (unwrapped SPDX strings); per-file annotation control intact (122/122); owned/tracked by Phase 2 (DEF-02-01/02) | Operator | 2026-06-20 |

*Accepted risks do not resurface in future audit runs.*

---

## Escalation Dispositions (ratified 2026-06-20)

These three findings are not Phase-1 implementation defects — each is a Phase-1 control that
later, deliberate Phase-2 work superseded or contradicted. The operator ratified all three.

### F1 — T-02-SC control superseded (no longer present)
Phase-1 disposition was "take **no** `github-copilot-sdk` dependency; wheel/lockfile SDK-free,
eliminating the issue-#1606 (CLI auto-update breaks transport) vector this phase." Current tree:
`github-copilot-sdk==1.0.2` is a pinned runtime dependency (resolved with hashes in `uv.lock`).
This is an expected Phase-2 step (the real adapter needs the SDK) and a pinned/hashed supply-chain
posture exists, but the #1606 vector the Phase-1 disposition claimed to *eliminate* is back in scope.
**Ratified:** accepted for Phase 1; re-mitigation (pin the SDK-compatible Copilot CLI version per the
stack mandate) is owned by the Phase-2 threat model. The "SDK-free" disposition is **not** carried
forward as if still true.

### F2 — "No REUSE.toml" prohibition reversed
Plans 01-01/01-02 prohibit a `REUSE.toml` (D-04: per-file annotation only). The tree now has a
`REUSE.toml` scoped to non-source meta (`.planning/**`, `.claude/**`, `.dogen/**`) at
`precedence = aggregate`, so per-file inline headers on real source still win and D-04-for-source is
preserved. Not a security hole. **Ratified:** the meta-only `REUSE.toml` is the accepted
interpretation of D-04; the Phase-1 plan prohibition is superseded for self-consistency of the trail.

### F3 — Standing LIC-01 gate (`reuse lint` → 0) currently RED
`uvx reuse lint` exits 1 on the current tree: 4 "Invalid SPDX License Expression" hits, all in
Phase-2 planning prose (`02-01-SUMMARY.md`, `02-02-SUMMARY.md`, `deferred-items.md`,
`01-VERIFICATION.md`) that quote the SPDX tag without `REUSE-IgnoreStart/End` wrapping. The Phase-1
*annotation* control (every file carries REUSE info → 122/122, Missing=0, Bad=0) is intact and no
source file is affected. **Ratified:** Phase-2 housekeeping debt, already logged as DEF-02-01/02;
the Phase-1 control needs no re-implementation. (This report wraps its own SPDX-bearing prose in
`REUSE-Ignore` markers so it does not add to the count.)

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-20 | 15 | 15 | 0 | gsd-security-auditor (opus) + operator ratification |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-20
<!-- REUSE-IgnoreEnd -->
