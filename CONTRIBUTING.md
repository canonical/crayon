# Contributing to dogen

Thank you for your interest in `dogen`. This guide covers how to propose changes and the
legal terms under which contributions are accepted. The binding engineering standard is
[`.planning/refs/coding-guide.md`](.planning/refs/coding-guide.md); coding agents are
additionally bound by [`AGENTS.md`](AGENTS.md).

## Contributor License Agreement (CLA)

Canonical requires a **Contributor License Agreement** with anyone contributing to a
Canonical project. Before your contribution can be merged, you must agree to the Canonical
CLA at:

> **<https://ubuntu.com/legal/contributors/agreement>**

A *trivial* change — one feasible to describe over the phone and apply correctly (for
example, a typo or whitespace fix) — does not require a CLA. Multi-line patches are usually
non-trivial and do require one.

Code contributed under the Canonical CLA is **not** copyright Canonical, but the file notice
must show that Canonical grants the license. CLA-contributed files therefore carry the
"License granted by Canonical Limited" notice variant rather than a
`SPDX-FileCopyrightText: 2026 Canonical Ltd.` line:

```
# This file is part of dogen, an agentic documentation-drafting framework.
# Copyright <year> <contributor>
# License granted by Canonical Limited
# SPDX-License-Identifier: GPL-3.0-only
# <...GPL warranty-disclaimer paragraph...>
```

See [`.planning/refs/licensing.md`](.planning/refs/licensing.md) §3.3 for the full notice
text. `dogen` is **GPL-3.0-only**; every file must be REUSE-compliant
(`reuse lint` gates CI).

## Branching, commits, and review

`dogen` follows a trunk-based model:

- **`main` is the default branch and is stable at all times.**
- **Feature branches** live about one pulse. Name them `docpr-<ticket>-<objective>`
  (kebab-case, alphanumeric, concise), or `<objective>` with no ID when there is no ticket.
- **Squash and merge** by default for a clean history; delete branches on merge.
- **Keep PRs small and reviewable.** Changes over ~1,000 lines are not viable to review.
- **Two maintainer reviews** are required before merge; a maintainer's own code is not
  exempt.
- **Request changes** rather than leaving mixed-signal comments; mark nitpicks explicitly.
- **Manual review, never spot-check:** reviewers check out the code and try the change
  locally. CI is necessary but not sufficient.

## Quality bar

Synthetic (AI-generated) code is held to **exactly** the same bar as hand-written code, and
the author who merges it owns it. Before opening a PR:

```bash
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run pytest
```

- **You own what you ship.** If you cannot explain what a unit of code does and *why*, it
  does not merge.
- **No regressions.** A change must not break something that worked before it.
- **Review generated comments and docstrings** as unverified claims — they are fluent and
  frequently wrong.
- For synthetic code, emit provenance per
  [`.planning/refs/synthetic-code-provenance.md`](.planning/refs/synthetic-code-provenance.md).

## Conduct

All participation is governed by our [Code of Conduct](CODE_OF_CONDUCT.md).

## Security

Do not report security vulnerabilities through public issues or pull requests. See
[SECURITY.md](SECURITY.md) for the reporting process.
