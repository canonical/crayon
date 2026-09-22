# Installing dogen

<!-- provenance: moved from README.md (Install and first run, Installing the skills globally, Add context files) -->

dogen is two things: one stdlib-only Python file, `dogen.py`, installed on your `PATH` as
`dogen`, and five portable Agent Skills
(`dogen-onboard`, `dogen-fetch`, `dogen-plan`, `dogen-write`, `dogen-review`) that your agent
drives. Installing means putting
the executable on your `PATH` and the skills where your agent discovers them. The script
`install.sh` at the root of the checkout does both, asks you about every choice along the way,
and verifies the result. This page explains each choice; if you are happy with the defaults, the
quickstart in `README.md` is all you need.

## Requirements

- Python 3.9 or newer on `PATH` as `python3`. Nothing else: no package, no venv, no dependency.
- git, and a git identity in the repository you document (`user.name` and `user.email`), because
  every dogen transition is a local commit.
- Any coding agent that reads `SKILL.md` skills and can run shell commands. Most discover
  them under `.agents/skills/`; the one common agent that reads only `.claude/skills/` is served
  by the symlinks the installer adds there. Skills are invoked by name — `/dogen-plan` — in every
  such agent.

## Install with the script

```bash
git clone https://github.com/akcano/dogen-mvp-1 ~/src/dogen
cd ~/src/dogen
./install.sh
```

The script walks through three decisions as numbered menus: type the number, or the option's
word. Enter takes the default at every prompt, and `./install.sh --yes` takes every default
without asking.

### 1. Where the skills go

- **project** (default) copies the five skills into `<repo>/.agents/skills/`, so they travel
  with the docs repository and every collaborator gets the same version, and links each one
  from `<repo>/.claude/skills/` for the agents that read only that root (commit the links too).
  The links are relative and computed between physical paths, so they resolve even when `.claude`
  is itself a symlink into a dotfiles checkout. The script asks for the
  repository (default: the current directory) and requires it to be a git repository already; it
  never runs `git init` for you. Re-run the install in each repository you document, and again
  after upgrading dogen.
- **global** copies them once into `~/.agents/skills/`, linked from `~/.claude/skills/`, so
  every repository on this machine discovers them. Choose this when you document many repositories alone and want one copy to
  upgrade.

Flags: `--skills project|global`, `--repo DIR`, `--skills-root DIR` for an agent that discovers
skills somewhere else, and `--no-compat-links` to skip the `.claude/skills/` links.

### 2. Where the executable goes

- `~/.local/bin` (default): a copy, no `sudo`, the usual place for a user's own tools. The script
  warns if that directory is not on your `PATH` and prints the line to add.
- `/usr/local/bin`: a copy for every user on the machine. The script does not run `sudo`; if
  the directory is not writable it says so and stops.
- **link**: a symlink from `~/.local/bin/dogen` into the checkout. `git pull` in the checkout
  upgrades the tool with no re-install, at the cost of a tool that changes underneath you when
  the checkout does. Good for trying dogen; use a copy for a repository other people rely on.
- Any other directory of your own.

Flags: `--tool-dir DIR`, `--link`.

### 3. `.gitignore`

dogen stages drafts under `.dogen/staging/`, which is working space and belongs in the
repository's `.gitignore`. With project-scoped skills the script offers to append that line;
`--no-gitignore` declines. Without it, `dogen verify` ends on a warning (V17) rather than a clean
verdict.

### Verification

The script always ends by checking the install and prints one line per check:

- `python3` is 3.9 or newer;
- `dogen` is where you asked, and `dogen` on `PATH` resolves to that file rather than to an
  older copy earlier on `PATH`;
- `dogen version --json` answers, and its `contract` number is the one each installed skill was
  written against (`metadata.dogen_contract` in its `SKILL.md`), compared as literal strings;
- each skill directory holds a `SKILL.md` and its `references/routing.md`;
- each `.claude/skills/` link resolves to the installed skill;
- no stale real copy of a skill sits in another discovery root (`.claude/skills/`,
  `.github/skills/`, `.opencode/skills/`), which an agent may find first;
- the repository has a git identity, and `.dogen/staging/` is ignored.

Failures exit 1; warnings do not. `./install.sh --verify-only` runs only this part against an
existing install, which is the thing to run when a skill stops on a version check.

## The scripted install, as the test suite runs it

The two fenced blocks below are the whole install, non-interactive, with every default. CI
extracts them byte for byte from between the two markers in this file and runs them from a
temporary `HOME` in a scratch repository (`tests/install_smoke.sh`),
so this section cannot rot. Run it in a repository you are prepared to install into.

<!-- INSTALL:BEGIN -->

```bash
DOGEN_SRC="${DOGEN_SRC:-$HOME/src/dogen}"   # your checkout of dogen
REPO="${REPO:-$PWD}"                        # the docs repo you are documenting
```

```bash
export PATH="$HOME/.local/bin:$PATH"
bash "$DOGEN_SRC/install.sh" --yes --repo "$REPO" --tool-dir "$HOME/.local/bin"
```

<!-- INSTALL:END -->

## Manual install

The script does nothing you cannot do by hand. The executable is one file; the skills are five
directories under `skills/`, and `cp -r skills/dogen-*` copies exactly those five and never
`skills/README.md`.

```bash
DOGEN_SRC=~/src/dogen

# The executable, onto your PATH, under its command name:
mkdir -p "$HOME/.local/bin" && cp "$DOGEN_SRC/dogen.py" "$HOME/.local/bin/dogen" && chmod +x "$HOME/.local/bin/dogen"

# The skills, project-scoped (run inside the docs repository):
mkdir -p .agents/skills && cp -r "$DOGEN_SRC"/skills/dogen-* .agents/skills

# ... or global:
mkdir -p "$HOME/.agents/skills" && cp -r "$DOGEN_SRC"/skills/dogen-* "$HOME/.agents/skills"

# For agents that read only .claude/skills/ (project form shown; use ~ for global):
mkdir -p .claude/skills && for s in dogen-onboard dogen-fetch dogen-plan dogen-write dogen-review; do ln -sfn "../../.agents/skills/$s" ".claude/skills/$s"; done

# Keep staging out of the record:
grep -qxF '.dogen/staging/' .gitignore 2>/dev/null || printf '.dogen/staging/\n' >> .gitignore
```

Then `./install.sh --verify-only` in the checkout, or `dogen version --json` by hand.

## Add context files (recommended)

Context files teach the skills your house style, vocabulary and where facts live. They are read
from `.dogen/context/` in the docs repository, and they reach it through the tool, which digests
and commits them. The quickest start is `/dogen-onboard` in your agent, which walks the docs you
already have and records `doc-style.md`, `glossary.md` and `structure.md`. A style guide or
glossary you already trust is recorded by hand in two commands:

```bash
dogen context stage doc-style.md --body-file path/to/your-style-guide.md
dogen context stage glossary.md --body-file path/to/glossary.md
dogen context record --note "house style and glossary, supplied by hand"
```

The five names, who produces each, `/dogen-fetch` for material outside the repository, and what
`/dogen-plan` does when the files are missing are all in [[context]].

## Uninstall

```bash
rm -f "$HOME/.local/bin/dogen"                  # or wherever you put it
rm -rf .agents/skills/dogen-*                   # project-scoped skills, per repository
rm -rf "$HOME/.agents/skills"/dogen-*           # global skills
```

The record under `.dogen/units/` is yours and stays: it is committed history, not part of the
install.

Related: [[context]], [[upgrade]], [[compatibility]], [[development]].
