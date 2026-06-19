# dogen

**An agentic documentation-drafting framework.**

`dogen` helps a Technical Author (or anyone acting in that capacity) draft complete,
review-ready documentation sets iteratively — faster than starting from scratch, with a
human owning intent and review at every step. It rides on an adopted agent SDK and adds a
thin doc-drafting layer on top: it does exactly one thing — **draft documentation in a
Sphinx-publishable format**.

## What it is

- **Type-aware drafting**, steered by human intent and product expertise.
- **Layered guidance**: org-wide guidance + per-repo knowledge + writer preferences.
- **Provider-agnostic by design**: the agentic backend (the Copilot SDK today) sits behind
  a thin, genuinely multi-provider seam so it can be swapped cheaply.
- **Sphinx-publishable output**: the primary docs-as-code stack is GitHub + Read the Docs +
  Sphinx (MyST Markdown), structured along Diátaxis.

## Scope border (the hard line)

`dogen` **drafts and stops at a singular, traceable local commit.** It deliberately stays
"dumb" outside drafting:

- It does **not** push, open or review pull requests, build, or auto-publish.
- A human owns intent and review of every draft; human-in-the-loop steering is mandatory
  and recorded.
- The reviewer/merger owns the shipped output — there is no AI content disclaimer, because
  humans stand behind what ships.

## Dev setup (quickstart)

`dogen` uses [`uv`](https://docs.astral.sh/uv/) for environments, dependencies, the
lockfile, and builds. Python **3.12** is the target.

```bash
# Create the environment and install the project with dev dependencies.
uv sync

# Lint and format (ruff) and type-check (ty).
uv run ruff check .
uv run ruff format --check .
uv run ty check

# Run the test suite (pytest + pytest-asyncio).
uv run pytest

# Build the distributable package.
uv build
```

`uv.lock` is committed — do not regenerate it casually; pin what you import.

## Project conventions

- **Operating contract for coding agents:** [`AGENTS.md`](AGENTS.md) — the non-negotiable
  invariants (the provider seam is sacred; you own what you ship; no regressions).
- **Coding guide:** [`.planning/refs/coding-guide.md`](.planning/refs/coding-guide.md) — the
  binding standard for all code, human- and machine-authored alike.
- **Licensing:** REUSE-compliant from commit 1. See
  [`.planning/refs/licensing.md`](.planning/refs/licensing.md) (the system of record) and
  [LICENSE](LICENSE).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Contributions require the Canonical Contributor
License Agreement (CLA).

## License

`dogen` is licensed under **GPL-3.0-only**. The full text is in [LICENSE](LICENSE) and
[`LICENSES/GPL-3.0-only.txt`](LICENSES/GPL-3.0-only.txt). Copyright 2026 Canonical Ltd.
