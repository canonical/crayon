# Engineering practice — extracted reference

**Status:** reference (faithful extraction). Complete substantive capture of Canonical's *Handbook for engineering practice in documentation*. The raw source is **ephemeral**; this file is the durable record.

- `dogen`'s **applied, enforceable** engineering standards live in [`coding-guide.md`](coding-guide.md). This file preserves the **full** handbook — including parts that are Sphinx-Starter-Pack–specific or not yet acted on — for traceability.
- **Omitted from the source:** base64 image slides and personal email addresses.
- **Stub sections** (headings present, no content in the source) are listed in §11 so nothing appears lost.

---

## 1. Decision log

- **2026-02-11 — Code review:** check out code and test manually; use *Request changes* for technical improvements; do **not** spot-check for technical changes.
- **2026-02-11 — Starter Pack versioning:** `<major>.<minor>`, no patch number; tag for major and minor; hotfixes = commits between tags; one major release per cycle; SP epic owner determines breaking changes for the roadmap; unplanned breaking changes are coordinated with the epic owner.
- **2026-02-11 — Starter Pack branching:** `main` only; delete `dev`; auto-delete branches after merge; clean up branches and PRs at end of cycle.

## 2. Active topics (owners)

- Hotfix policy — JJ Coldiron
- Breaking changes policy — JJ Coldiron
- Agentic development practice — Michael DuBelko

## 3. Branching practices

### All projects
- **Default branch:** `main`.
- **Protected branches:** `main` and development branches are protected; all PRs to them need **two maintainer approvals**.
- **Branch naming:** concise; with a Jira ticket / GitHub issue → `docpr-123-fix-spelling-check`; without → `fix-spelling-check`.
- **Feature branches:** typically live ~2 weeks / one pulse; live for the lifetime of their PR. Long-lived refactor/redesign branches are permitted only when there's no other option, and are ardently discouraged.
- **Branch hygiene:** commits squashed by default during merge; merge commit only when preserving atomic history matters; follow-up commits after approval **dismiss** the review; auto-delete feature branches after merge; never restore a merged branch; once per cycle maintainers close stale PRs and delete their branches.
- **Forking:** external contributors can't create branches on the repo — they propose from a personal fork.

### Sphinx Starter Pack specifics (context, not `dogen`'s model)
- The SP is a **template repository**, not an immutable package; distributed by copying the state of `main`. Trunk-based development with some GitHub-flow elements. `main` is both the release and development branch; releases are **tags**.
- **Rationale:** users can copy `main` at any time, so it needs live hotfixes; splitting code across branches creates disjoint history graphs.
- Near-term SP plan: merge against `main`; no `dev`; users copy `main`; tag releases for systems that need them (upgrade guides/scripts, CI); RTD builds from `main` → publishes to `latest`.
- Future repo split: core template repo = trunk-based; SP docs/dev repo = "Gitflow Lite".
- **Merging (SP):** squash and merge; clean CI before merge; repo-owner approval(s); dismiss stale approvals on new commits.

## 4. Code rules

- Reading reference: NASA/JPL **"Power of Ten"** (`spinroot.com/gerard/pdf/P10.pdf`).
- Proposed: **no function longer than one printed page** (~60 lines, one statement per line, one declaration per line).
- **No code introduces a regression** (breaking something that worked before the change).

## 5. Roles (source: headings only)

Admins · Core maintainers (Starter Pack, Extensions) · CODEOWNERS — structure named in the source, details not yet written.

## 6. Code review practice

A successful review makes the software better for the **user**, builds the **developer's** skill, gives the **reviewer** understanding of the new code, and leaves the **project** with high-quality code.

- **Scope and timing:** reviews are timely to the task; roadmap/commitment work takes priority. A timed item can expect two maintainer reviews within a week of opening, aiming to merge before the pulse ends. An unscheduled modest contribution can expect an initial review within two weeks. **Unscheduled changes over ~1,000 lines aren't viable to review** — no expectation they'll be reviewed.
- **Mandatory reviewers:** all code needs **two maintainer reviews** before merge; maintainer-authored code is not exempt. Maintainers are encouraged to **Request changes** (a blocking review is a forcing function; "comments" sends mixed signals).
- **Optional reviewers:** domain experts are invited (sometimes via `CODEOWNERS`, but human judgement is the best heuristic). Non-experts may review if focused; pure-nitpick reviews can derail a timely merge. Reviewers should **mark nitpicks** so required vs optional is clear.
- **Checks during a review:** code is checked from two sources — CI (automated, high trust but intractable practical/theoretical limits) and the reviewer (manual). **Maintainer reviews must be manual, not spot checks:** check out the code locally and try the change (UX, fuzz/smoke, cross-platform). If the description is insufficient to understand/test, request more detail first.
- **Review sequence:** maintainers auto-assigned via `CODEOWNERS`; reviewer tests locally and leaves comments/inline suggestions. Contributors push follow-up commits to their branch (preferably not via the GitHub UI — keeps the workflow uniform, reduces fork-sync mistakes and merge conflicts). Force-pushing after approval is heavily discouraged (hides what changed).

## 7. Machine-assisted development

> The applied, enforceable form of this section is in [`coding-guide.md`](coding-guide.md) §§2–5. The raw critique lists are preserved verbatim below because they are the source's unique content.

Coding agents and LLMs are non-deterministic, with high variation between implementations; applying them consistently "needs serious study." Adoption is a **company mandate** — but applied with rigour, not "unchecked excitement." *"Regardless of where our code comes from … we aren't exempt from correct and safe software development."*

### General machine-assisted guidelines — for synthetic code:
- Produce a **globally-reusable prompt** for all systems that outputs: the **timestamp**, the **harness name**, the **model and mode**, the **full anatomy** (skills, instructions, user decisions, prompts, examples), and the **token cost** for the last operation.
- Focus on common languages with shared group understanding: **Python and Bash**.
- Prioritize comments that outline modules and, above all, the **why** of code units — for human and machine comprehension. *"If we can't understand what the code is doing, we can't be responsible for it."*
- **Review automatically-generated comments** — synthetic comments can sound plausible but be benign, meaningless, or incorrect.
- Run a common set of linters/formatters: **Ruff** and **ty** for Python.
- Produce/source a small **Bash style guide**. GLM-5.1 Hackathon Bash weaknesses: no comments; rule-of-three violations; pre-emptive variables; commands that should be stored once but were re-called (and could mutate between calls); repeated sequences not wrapped in functions; unreadable shell ops (complex `sed`); excessive if-then chains; decomposed strings; writing to console one line at a time; outdated conditional syntax (`[]`); generally disorganized code (variables/functions declared only for the immediate context); excess directory structures; inconsistent directory naming; nonsense operations (`true > file.txt`).
- Produce/source a small **Python style guide**. Hackathon Python weaknesses: high cyclomatic complexity; traditional if-else blocks to assign a single value; functions with too many exit points; unnecessarily loose typing (`typing.Any`); docstrings lacking parameter/return descriptions; overuse of inline comments; inflexible functions only called once; monolithic modules and classes; rigid and bespoke testing logic; overuse of mocks in testing; arbitrary dependency constraints; wrapping other languages; tight coupling between modules/classes/functions; no common decorators; aversion to basic data structures.

### Reusable operations
*Operations an LLM/agent runs more than once* (a scheduled CI task, an on-demand workflow to build tests). When building one:
- Store it in a freely-editable workspace (GitHub repo or Google Doc).
- Test it works with a **fresh context and without caching**.
- Test against **disparate inputs**: reST and Markdown sets, different Python extensions, workflows in different repos.
- Test against **models from competing vendors**.
- Create **allowlists for shell commands** in skills. (Anthropic models are quick to resort to shell for basic questions/discovery — in many cases failing simple globs to list files. Arbitrary shell risks data loss and out-of-bounds behaviour on user hosts and CI runners.)
- Document it: a correct/complete example output; the full anatomy (skills, instructions, user decisions, prompts, examples); harnesses used; models tested; result variation between models; the input data tested against; token cost with and without caching; a test date.

### Choosing the right solution
Agents handle complex/variable tasks in different environments; LLMs handle NL processing and text generation; traditional software gives deterministic results. Choose the best tool — consider: Is the task a predictable process with no step variation? High edge-case variability in input? Near-natural text reading/interpretation needed? Must it operate inside the host like a user?

### Testing and replicability
Sub-topics named in the source: **Determinism**, **Model variation**, **Model drift**, **Guardrails**. On guardrails: in Anthropic's Mythos Preview the model raised organic guardrails that pushed back on legitimate security research, and these refusals were **inconsistent** (the same task framed differently could pass or refuse). Echoed in the team's own Claude Sonnet 4.6 testing — guardrails could be bypassed trivially. Implication: some models raise guardrails on legitimate dev tasks, and there may be a class of guardrails we can deterministically program around — needs model-by-model exploration.

### Community use / Explainability (auditability) / Token cost
Named as TODO in the source.

## 8. Architecture for Sphinx systems (open questions in the source)

- What are the boundaries between Sphinx systems? (GitHub workflows, Read the Docs workflows, Starter Pack → Sphinx → theme, extensions.)
- What are the components? What is their relationship (inheritance model)? How do they interact (when coupled vs interfaced)? What are the primary means of consumption and reuse between components?

## 9. Versioning policy

- **Sphinx extensions:** Semantic Versioning 2.0 — `MAJOR.MINOR.PATCH` (breaking / new non-breaking / hotfix).
- **Sphinx Starter Pack:** modified SemVer `MAJOR.MINOR` (no patch represented; each commit between tags is nominally a patch identified by SHA). Because users copy `main` anytime, every commit is effectively a working version / unofficial atomic release.
- **Semantic meanings (SP):**
  - **Major** — change that, if ignored/overridden, greatly affects doc quality or compatibility; also dropping a feature/support; sometimes incorporating a nontrivial upstream breaking change. Mandatory, often significant user effort, planned and implemented by maintainers, raised in all communications before release.
  - **Minor** — a new optional feature; if ignored, no negative effect; may require trivial user action (e.g. overriding a new config option's default).
  - **Patch** — corrects existing behaviour/information; trivial to incorporate. Not tagged, but every commit to the default branch is effectively a patch and must be tested and documented thoroughly.

## 10. Release process & notes model (Starter Pack)

**Process:** (1) *Coordinate and collect* — assemble deprecations (major) or ensure changes merged+documented (minor); clear the release with the "Documentation tooling" cohort. (2) *Prepare code* — branch `release/<version>`; set `docs/version`; for major, remove planned-deprecated features (trivial → commit directly; nontrivial → sub-branch + PR); write release notes. (3) *Test and review* — open PR, fix failing checks, resolve review issues. (4) *Publish* — merge; sync local `main`; `git tag X.Y -s -m "Release X.Y"`; `git push --tags`; create a GitHub release with the notes; post notes to Discourse and the `~authors` / `~documentation` Mattermost channels with a link to the GitHub release.

**Release-notes model:**
- *Major:* What's changed since (X-1).0; New features (with `conf.py` snippets); Breaking changes; Dependency changes; Complete changelog; Feature deprecations; Bug fixes; Contributors.
- *Minor:* What's new in X.Y; Dependency changes; Deprecated; Fixed; Contributors.

(These templates are illustrative and Starter-Pack–specific.)

## 11. Empty stub sections in the source

These headings exist with **no content** in the handbook (recorded so their absence is explicit, not an extraction gap): Code quality standards · Repository labels · Contribution responsiveness · Reliability · Support and maintenance policy · Breaking changes policy · Deprecation best practices · Testing policy · Testing best practices · CI policies · CI workflow best practices · Issue responsiveness · Safety · Security policy · Vulnerability response process · Code safety best practices · Distribution · Sphinx extensions (branching) · Scripts and workflows (branching) · Principles · What engineering means · Software values · Rules we abide by.

---

## 12. Source provenance

Extracted from **"Handbook for engineering practice in documentation"** (Canonical). The raw source is ephemeral; this file is the durable record. Base64 image slides and personal email addresses omitted; stub sections noted in §11.
