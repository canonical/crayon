# dogen

**dogen** is a platform-agnostic, agentic **documentation-drafting** framework for Technical
Authors. It drafts review-ready, **Sphinx-publishable** documentation (MyST Markdown or
reStructuredText, Diátaxis-structured) from human-pointed sources — human-in-the-loop — and
deliberately stops at the boundary of a single traceable local commit.

This iteration is a **skills-first rebuild**: portable Agent Skills (`SKILL.md`) are the
surface a Technical Author drives, layered over a deterministic Python core.

- **Skills-first surface** — the portable `dogen-plan` / `dogen-write` / `dogen-review`
  skill family is the primary, harness-agnostic human interface (Claude Code, Copilot CLI,
  opencode, and any harness that reads `SKILL.md`).
- **Type-aware drafting**, steered by human intent, audience, and product expertise.
- **Provider-agnostic by design** — the agentic backend (the GitHub Copilot SDK today) sits
  behind a thin, genuinely multi-provider seam so it can be swapped cheaply.
- **Sphinx-publishable output** — the target docs-as-code stack is GitHub + Read the Docs +
  Sphinx, structured along Diátaxis.

## Scope border (the hard line)

dogen **drafts and stops at a single, traceable local commit.** It stays deliberately "dumb"
outside drafting:

- It does **not** push, open or review pull requests, build, or auto-publish.
- A human owns intent and review of every draft; human-in-the-loop steering is **mandatory
  and recorded** — dogen refuses to produce a substantial draft without it.
- The reviewer/merger owns the shipped output — there is no "AI-generated" disclaimer,
  because humans stand behind what ships.

---

## Quickstart: use dogen in a docs repo

### 0 — Set up your environment

dogen is an agentic system still in development. It is recommended that testing
be done in an isolated environment to limit the potential for loss or corruption
of data. To create a new environment for testing:

- Install LXD and [create a new container](https://canonical.com/lxd/docs/latest/tutorial/first_steps/#create-and-start-containers).
- Start the container and create a working folder for your documentation generation project inside it.
- Initialize git, i.e., `git init` and set up your identity - some skills may otherwise not run properly.
- Create an ssh key in the container so you can install dogen from GitHub. A **read-only**, repo-scoped
  [deploy key](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/managing-deploy-keys#deploy-keys)
  is preferable.
- Push all necessary files and directories from your [local machine into the working folder](https://canonical.com/lxd/docs/latest/howto/instances_access_files/#push-files-from-the-local-machine-to-the-instance), e.g., docs repo, code, and artefacts from code-to-docs mapper and onboarding scraper.
- If you plan to use Copilot, OpenRouter, or any other cloud based system, you will be prompted to authenticate your
  session.
- [Install uv](https://docs.astral.sh/uv/#installation).

**Alternative: use [`workshop`](https://github.com/canonical/workshop)**, Canonical's
"secure, fast, and composable" agent-ready dev-environment tool
([snapcraft.io/workshop](https://snapcraft.io/workshop)). It replaces the container-creation
and file-transfer bullets above with a definition file and a couple of commands:

- Install it: `sudo snap install workshop --classic`.
- Launch the environment this repo already declares in
  [`.workshop/dogen-dev.yaml`](.workshop/dogen-dev.yaml) (it declares the `uv` SDK, so
  there's no separate "install uv" step): `workshop launch dogen-dev`.
- Get a shell inside it — `workshop shell dogen-dev` (or run one-off commands with
  `workshop exec dogen-dev -- <command>`). The project directory is mounted automatically
  at `/project` inside the workshop, so there's no manual file-push step either.
- Set up your git identity inside the workshop the same way as above — `$HOME` isn't
  shared with the host, so `git config --global user.name`/`user.email` still need setting.
- Create an ssh deploy key inside the workshop the same way as above, so you can install
  dogen from GitHub.
- If you plan to use Copilot, OpenRouter, or any other cloud based system, you'll be
  prompted to authenticate your session, same as above.
- Optionally, add your agent harness's own CLI as an SDK too — workshops come
  agent-ready, and the SDK Store carries sandboxed, credential-persisting builds for all
  three harnesses dogen ships skills for:
  [`claude-code`](https://github.com/canonical/claude-code-sdk),
  [`copilot`](https://github.com/canonical/copilot-sdk), and
  [`opencode`](https://github.com/canonical/opencode-sdk). Add the ones you use with
  `workshop init <name> --sdks uv,claude-code,copilot,opencode` (check what's on offer
  with `sdk find <query>` / `sdk info <name>` from the `workshop.sdk` snap app).

### 1 — Install the `dogen` CLI

dogen isn't on a public package index yet — install it from this repository with
`uv`:

```bash
# Install the CLI as a uv tool (isolated, on your PATH):
uv tool install git+ssh://git@github.com/canonical/dogen-mvp-1

# …or from a local checkout / built wheel:
#   uv build && uv tool install dist/dogen-*.whl

dogen --help          # verify the install
```

**Provider setup (optional).** By default dogen uses the zero-setup **host-harness passenger**
provider — your own agent authors the draft and dogen records it. To use the **GitHub Copilot
driver** (generation in-process behind a read-only toolset), fetch its runtime once and select
it explicitly:

```bash
python -m copilot download-runtime        # one-time, pins the Copilot CLI runtime
dogen provider set copilot                # or: export DOGEN_PROVIDER=copilot, or --provider
```

Provider selection is always explicit — flag > `DOGEN_PROVIDER` > repo config > `host-harness`;
there is no silent fallback.

### 2 — Install the skills into your agent

Run from the **root of the docs repo** you want to draft in:

```bash
dogen skills install --harness claude     # repeatable: --harness copilot --harness opencode
#                                         # …or omit --harness to auto-detect present harnesses
dogen skills status                       # show each install's drift vs the canonical family
dogen skills update                       # re-stage after upgrading dogen
```

Each harness has its own discovery root:

| Harness | Skills land in |
|---------|----------------|
| `claude`   | `.claude/skills/` |
| `copilot`  | `.github/skills/` |
| `opencode` | `.opencode/skills/` |

The install is recorded in `.dogen/skills-install.yaml`. Your agent now sees the
`dogen-plan`, `dogen-write`, and `dogen-review` skills. `skills/` is the single source of
truth — re-run `dogen skills update` rather than hand-editing an installed copy.

### 3 — Add context files (recommended)

Context files teach dogen your house style, vocabulary, and where facts live. They land in the
**`.dogen/context/`** zone; add each with `dogen context add`, which files **and commits** it:

```bash
dogen context add path/to/your-style-guide.md --as doc-style.md
dogen context add path/to/glossary.md         --as glossary.md
dogen context ls                              # list what's landed
```

`--as` sets the landing filename (defaults to the source file's name; pass `--no-commit` to
stage without committing). Free-form names are welcome, but a set of **well-known names** is
what the skills look for by default:

| File | What it holds |
|------|---------------|
| `doc-style.md`        | Voice, register, and house style |
| `glossary.md`         | Preferred terms and vocabulary |
| `structure.md`        | Section / page structure conventions |
| `code-to-docs-map.md` | Map from code areas to the concepts that document them (grep-first; can be large) |
| `doc-gaps.md`         | Known documentation gaps |

To include organization-wide guidance in the agent's context, create a directory called `optional-guidance`
at the root of your project and add the relevant files. Expected files include style guides,
syntax guides, framework guides (Diataxis), and similar guidance. Any context added here is
considered optional and is mainly intended to augment the 'knowledge' of less-capable models.

### 4 — Draft a documentation unit

Drive the three skills in order from your agent. They call the deterministic dogen verbs and
enforce the human-in-the-loop gate at each step:

1. **`dogen-plan`** — declare a unit and its sources, shape the outline, record your **intent
   and audience** steering, and **sign the plan off**.
2. **`dogen-write`** — draft the page(s) from the signed-off plan, grounded in the declared
   sources and steered by what you recorded.
3. **`dogen-review`** — review the draft alongside its provenance and record a verdict
   (**accept** / **fix** / **redraft**).

The gate is enforced in code, not by convention: `dogen draft` refuses — with no side effects —
until intent/audience steering **and** a signoff are on record. When you're done, the draft sits
in **one local commit** for you to review and merge. dogen never pushes.

> **Power users / CI:** the same operations are callable directly —
> `dogen unit new`, `dogen signoff`, `dogen steer`, `dogen draft`, `dogen review`,
> `dogen status`, `dogen unit show`. The skills are the recommended path; the CLI is the
> always-available fallback. Run `dogen --help` for the full verb set.

### Vocabulary

A few terms recur across the skills and the provenance record:

- **sealed** — a unit whose latest verdict-bearing review is an **accept**. Sealing is
  *derived* from the review history, never stored as a flag; a later `fix`/`redraft`
  verdict reopens the unit (see dogen-review).
- **lease** — a unit owns (claims) its target pages only *while it is in flight*.
  Accepting the unit **releases** the lease, so another unit may then claim the page;
  an in-flight unit's pages stay claimed and a competing declare/edit is refused
  (`target_claimed`).
- **supersede** — a seal attests the text accepted at that moment; a later unit may
  supersede it; digests + git trailers order the seals. Declaring or editing onto a
  page a sealed unit owns records the supersede as an `extends:` body line and a
  `Dogen-Extends: <owner-id>` commit trailer.

---

## Develop dogen itself

dogen uses [`uv`](https://docs.astral.sh/uv/) for environments, dependencies, the lockfile, and
builds. Python **3.12** is the target.

```bash
# Create the environment and install the project with dev dependencies.
uv sync

# Lint and format (ruff) and type-check (ty).
uv run ruff check .
uv run ruff format --check .
uv run ty check

# Enforce the provider seam (AST guard + import-linter) and lint the skills.
uv run python scripts/seam_check.py
uv run python scripts/skill_lint.py
uv run lint-imports

# Run the test suite (pytest + pytest-asyncio).
uv run pytest

# Build the distributable package.
uv build
```

The provider seam is the load-bearing invariant: `dogen.core` never imports a provider SDK or a
concrete telemetry backend. See [`AGENTS.md`](./AGENTS.md) for the full operating contract and
stack rationale.

## Validation

dogen has been exercised end-to-end across three agent harnesses. See
[`validation/round-3-report.md`](./validation/round-3-report.md) for the latest report (Sphinx
builds, output-vs-gold comparison, and provenance), with the per-leg captures under
[`validation/round-3/`](./validation/round-3/).

## Project timeline

An interactive milestone planning timeline lives in
[`project-timeline.html`](./project-timeline.html) — pulses by component, with dependency
links and per-item detail. It's a standalone page (inline CSS/JS, no build step). GitHub
shows it as source; view it by opening the file in a browser, or on the repo's
(access-controlled) GitHub Pages site at
<https://effective-doodle-ee1w8gm.pages.github.io/project-timeline.html>.

## Licensing

The packaged core is licensed under **LGPL-3.0-only** (see [`LICENSE`](./LICENSE)). The portable
skills under [`skills/`](./skills/) are licensed separately under **Apache-2.0** (see
[`skills/LICENSE`](./skills/LICENSE)).
