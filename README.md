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

### Prerequisites & assumptions

This walkthrough runs everything inside a disposable **Workshop** environment and names what it
needs, so your host stays clean and a fresh box works on the first try. It assumes:

- **[Workshop](https://github.com/canonical/workshop) on your host** — Canonical's "secure, fast,
  and composable" ([snapcraft.io/workshop](https://snapcraft.io/workshop)), LXD-backed
  dev-environment tool. dogen drives an autonomous agent that reads and writes files and runs
  commands on your behalf, so isolate it from anything you can't afford to lose; a Workshop is
  exactly that throwaway boundary. Install it once: `sudo snap install workshop --classic`.
- **The runtime and harness come from SDKs, not your host.** Workshop layers `uv` (which provides
  Python 3.12+) and your agent harness into the container for you, so there's no system Python,
  Node.js, or `PATH` setup to do by hand.
- **git with an identity** — set *inside* the workshop (its `$HOME` isn't shared with the host);
  dogen records every step as a local commit.
- **A docs repository to draft in** — a Git repo with a Sphinx/Diátaxis docs tree (or where you
  intend to start one), plus any code or artefacts you want documented. Your project mounts into
  the workshop automatically at `/project`.
- **Outbound network access**, and **optional provider credentials** — the latter only if you
  switch from the default host-harness passenger to the Copilot *driver* (see step 1).

### 0 — Set up your environment

dogen is an agentic system still in development, so run your testing in an **isolated environment**
to limit any potential for loss or corruption of data.
[Workshop](https://github.com/canonical/workshop) gives you a disposable, LXD-backed container and
layers in everything dogen needs as **SDKs** — no base-package, Node.js, `uv`, or `PATH` setup to
do by hand:

1. **Install Workshop** on your host: `sudo snap install workshop --classic`.
2. **Define a workshop in your docs repo.** `workshop init dogen-dev --sdks uv,copilot --base
   ubuntu@24.04` scaffolds [`.workshop/dogen-dev.yaml`](.workshop/dogen-dev.yaml), layering the
   `uv` and **GitHub Copilot CLI** SDKs. (This repo already ships that file with both SDKs, so you
   can skip straight to the launch below.) Prefer Claude Code or opencode? Their SDKs are in the
   Store too — swap the `copilot` entry, and check what's on offer with `sdk find <name>` /
   `sdk info <name>` (or `workshop.sdk …` if `sdk` isn't on your `PATH`).
3. **Launch it:** `workshop launch dogen-dev`. This builds the container, runs the SDK setup, and
   mounts your project at `/project` inside the workshop.
4. **Get a shell inside it:** `workshop shell dogen-dev` (or run one-off commands with
   `workshop exec dogen-dev -- <command>`). **Every step from here on runs inside the workshop.**
5. **Set your git identity** — `git config --global user.name "…"` and
   `git config --global user.email "…"`. The workshop's `$HOME` isn't shared with the host, and
   dogen commits every transition, so this needs setting inside.
6. **Authenticate your harness** — launch `copilot` and run `/login` (credentials persist in the
   workshop). With the default `host-harness` provider your harness is the passenger that authors
   drafts, so this single login is the only credential you need. Using Claude Code or opencode
   instead? Authenticate it the same way and pass `--harness claude` / `--harness opencode` when
   you install the skills below.
7. **Installing dogen from a private repo?** Add a **read-only, repo-scoped**
   [deploy key](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/managing-deploy-keys#deploy-keys)
   inside the workshop, and accept GitHub's host key once with `ssh -T git@github.com`, so
   installing the dogen CLI (next) doesn't stall.

### 1 — Install the `dogen` CLI

Run this and the remaining steps **inside the workshop** (`workshop shell dogen-dev`). dogen isn't
on a public package index yet — install it from this repository with `uv` (already provided by the
workshop's `uv` SDK):

```bash
# Install the CLI as a uv tool (isolated, on your PATH):
uv tool install git+ssh://git@github.com/canonical/dogen-mvp-1

# …or from a local checkout / built wheel:
#   uv build && uv tool install dist/dogen-*.whl

dogen --help          # verify the install
```

If a fresh shell reports `dogen: command not found`, put uv's tool directory on your `PATH` with
`uv tool update-shell` (or add `~/.local/bin`) and reopen the shell.

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

Run from the **root of the docs repo** you want to draft in (inside the workshop, that's `/project`):

```bash
dogen skills install --harness copilot    # repeatable: --harness claude --harness opencode
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

### Confirm your setup works (smoke check)

Still inside the workshop, prove the plumbing end-to-end before pointing dogen at real docs. The
credential-free `mock` provider drafts deterministically in-process, so nothing here needs a
harness login or a provider token, and nothing touches your docs repo:

```bash
dogen --help                 # the CLI is installed and on your PATH
dogen provider show          # resolves to host-harness (from default)

# Drive one throwaway unit through the full gate in a scratch repo:
mkdir /tmp/dogen-smoke && cd /tmp/dogen-smoke && git init -q
printf '# Widget API\n\nThe widget API exposes create and delete.\n' > source.md
git add -A && git commit -q -m "seed source"

dogen unit new smoke --intent reference --title "Smoke" --source source.md --target smoke.rst
dogen steer smoke --note "Audience: developers evaluating dogen; keep it terse."
dogen signoff smoke
dogen draft smoke --provider mock          # writes docs/smoke.rst
dogen review smoke --verdict accept --note "smoke"
dogen status                               # smoke -> reviewed, signoff yes
```

If every command exits cleanly and `dogen status` shows `smoke` at `reviewed`, your environment is
wired up — the same `unit new → signoff → draft → review` gate runs for real in steps 3–4. As a
last check, from your **docs-repo root** open your harness (`copilot`) and confirm it lists the
`dogen-plan`, `dogen-write`, and `dogen-review` skills you installed above. Clean up the scratch
repo when done: `rm -rf /tmp/dogen-smoke`.

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

Drive the skills in order from your agent. They call the deterministic dogen verbs and
enforce the human-in-the-loop gate at each step. `dogen-plan` opens and `dogen-review` closes
**every** direction; only the middle drafting step branches by the unit's declared Diátaxis
direction:

1. **`dogen-plan`** — declare a unit and its sources, shape the outline, record your **intent
   and audience** steering, and **sign the plan off**. This is also where the direction is
   declared, which routes the drafting step below.
2. **Draft — by direction:**
   - **reference** → **`dogen-write`** — draft the page(s) from the signed-off plan, grounded
     in the declared sources and steered by what you recorded.
   - **tutorial / how-to** → **`dogen-record`** — drafted by *doing*: an interactive,
     evidence-gated step walk that captures verbatim proof as each step runs (redirected output
     bytes, a real exit code, a SHA-256) and authors the page from what actually ran, not from
     static sources.
   - **explanation** → **`dogen-plan`**'s intent walk (the 5-whys, understanding-first mode) to
     draw out and record the *why*, then **`dogen-write`** drafting with an explanation stance.
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
