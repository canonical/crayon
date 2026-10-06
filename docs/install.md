# Installing dogen

<!-- provenance: moved from README.md (Install and first run, Installing the skills globally, Add context files); reordered to put the manual install first -->

dogen has two parts:

- the `dogen` tool: one Python file, `dogen.py`, installed on your `PATH` as `dogen`;
- five Agent Skills: `dogen-onboard`, `dogen-fetch`, `dogen-plan`, `dogen-write` and
  `dogen-review`. Your agent runs them, and they use the tool.

To install dogen, put the tool on your `PATH` and the skills where your agent finds them. You
can do this by hand in a few commands, or run the installer, `install.sh`.

## Requirements

- Python 3.9 or newer, available as `python3`. Nothing else: no package, no virtual
  environment, no dependency.
- git. Your docs repository must have a git user name and email (`user.name` and
  `user.email`), because dogen makes a local commit for every step.
- A coding agent that can use Agent Skills (`SKILL.md` files) and run shell commands. Most
  agents find skills under `.agents/skills/`. Some read only `.claude/skills/`, so step 4 below
  links the skills there too. You run a skill by its name, for example `/dogen-plan`.

## Install by hand

1. Download dogen:

   ```bash
   git clone https://github.com/canonical/dogen ~/src/dogen
   ```

2. Install the tool:

   ```bash
   mkdir -p ~/.local/bin
   cp ~/src/dogen/dogen.py ~/.local/bin/dogen
   chmod +x ~/.local/bin/dogen
   ```

   Check it: `command -v dogen` must print a path. If it prints nothing, add this line to your
   shell profile (for example, `~/.bashrc`) and open a new terminal:

   ```bash
   export PATH="$HOME/.local/bin:$PATH"
   ```

3. Install the skills. Choose one place.

   In your docs repository (recommended). The skills travel with the repository, and your
   collaborators get the same version:

   ```bash
   cd /path/to/your-docs-repo
   mkdir -p .agents/skills && cp -r ~/src/dogen/skills/dogen-* .agents/skills/
   ```

   Or once for your user, so that every repository on this machine finds them:

   ```bash
   mkdir -p ~/.agents/skills && cp -r ~/src/dogen/skills/dogen-* ~/.agents/skills/
   ```

   `dogen-*` matches exactly the five skills. It does not copy `skills/README.md`, which is not
   a skill.

4. Link the skills from `.claude/skills/`, for the agents that read only that folder.

   In your docs repository:

   ```bash
   mkdir -p .claude/skills
   (cd .claude/skills && ln -sf ../../.agents/skills/dogen-* .)
   ```

   Or for your user:

   ```bash
   mkdir -p ~/.claude/skills
   ln -sf ~/.agents/skills/dogen-* ~/.claude/skills/
   ```

   If `.claude` in your docs repository is itself a symlink, use the installer instead. It
   computes links that work from where `.claude` really is.

5. In your docs repository, tell git to ignore the folder where dogen keeps unfinished drafts:

   ```bash
   echo '.dogen/staging/' >> .gitignore
   ```

6. If you installed the skills in the docs repository, commit `.agents/skills/`,
   `.claude/skills/` and `.gitignore`, so that your collaborators get them.

7. Check the install. Run this in your docs repository. It changes nothing:

   ```bash
   ~/src/dogen/install.sh --verify-only --yes
   ```

   For skills installed for your user, add `--skills global`.

## Install with the script

The installer does the same steps as the manual install. Run it from your docs repository:

```bash
cd /path/to/your-docs-repo
~/src/dogen/install.sh
```

It asks three questions. Type the number or the word of an option. Enter takes the default.
`--yes` takes every default without asking.

### 1. Where the skills go

- **project** (default): copies the five skills into `<repo>/.agents/skills/` and links each
  one from `<repo>/.claude/skills/`. The skills travel with the docs repository, and every
  collaborator gets the same version; commit the copies and the links. The links are relative
  and computed between physical paths, so they work even when `.claude` is a symlink into a
  dotfiles checkout. The script asks for the repository (default: the current directory). The
  repository must already be a git repository; the script never runs `git init`. Run the
  install again in each repository you document, and again after you upgrade dogen.
- **global**: copies the skills once into `~/.agents/skills/` and links them from
  `~/.claude/skills/`. Every repository on this machine finds them. Choose this when you
  document many repositories alone and want one copy to upgrade.

Flags: `--skills project|global`, `--repo DIR`, `--skills-root DIR` for an agent that finds
skills somewhere else, and `--no-compat-links` to skip the `.claude/skills/` links.

### 2. Where the tool goes

- `~/.local/bin` (default): a copy. No `sudo`. This is the usual place for your own tools. The
  script warns if this folder is not on your `PATH` and prints the line to add.
- `/usr/local/bin`: a copy for every user on the machine. The script does not run `sudo`. If
  you cannot write to the folder, the script says so and stops.
- **link**: a symlink from `~/.local/bin/dogen` to the file in your checkout. `git pull` in the
  checkout then upgrades the tool without a new install. The tool also changes whenever the
  checkout changes, so use a copy for a repository other people rely on.
- Any other folder of your own.

Flags: `--tool-dir DIR`, `--link`.

### 3. `.gitignore`

dogen keeps unfinished drafts under `.dogen/staging/`. This folder is working space and
belongs in the repository's `.gitignore`. For project skills, the script offers to add the
line. `--no-gitignore` declines. Without the line, dogen's checks report a warning.

### What the script checks

At the end, the script checks the install and prints one line per check:

- `python3` is 3.9 or newer;
- the `dogen` tool is where you asked, and the `dogen` found on your `PATH` is that file, not
  an older copy earlier on your `PATH`;
- the tool runs and reports its version and contract number, and the contract number is the one
  each installed skill was written for (`metadata.dogen_contract` in its `SKILL.md`, compared
  as a literal string);
- each skill folder holds its `SKILL.md` and `references/routing.md`;
- each link in `.claude/skills/` points to the installed skill;
- no old copy of a skill sits in another skills folder (`.claude/skills/`, `.github/skills/`,
  `.opencode/skills/`), where an agent may find it first;
- the repository has a git user name and email, and `.dogen/staging/` is ignored.

A failed check makes the script exit with code 1. A warning does not.
`install.sh --verify-only` runs only the checks. Run it when a skill stops on a version check.

Last, the script prints the commands that remove what it installed, with your exact paths.
Keep them if you may want to uninstall later. The generic form is under
[Uninstall](#uninstall).

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

## Add context files (recommended)

Context files teach the skills your house style, your terms and where facts live. To create
them, open your agent in the docs repository and run `/dogen-onboard`. It reads the docs you
already have.

If you already have a style guide or a glossary, run `/dogen-fetch` and give it the file path
or the URL. The five context files, and what `/dogen-plan` does when they are missing, are in
[[context]].

## Uninstall

The installer prints these commands with your exact paths. For the default places, they are:

```bash
rm -f ~/.local/bin/dogen
```

For skills in a docs repository, run this in the repository, then delete the line
`.dogen/staging/` from its `.gitignore`:

```bash
rm -rf .agents/skills/dogen-*
rm -f .claude/skills/dogen-*
```

For skills installed for your user:

```bash
rm -rf ~/.agents/skills/dogen-*
rm -f ~/.claude/skills/dogen-*
```

Uninstalling leaves your pages and the record under `.dogen/` in place. They are committed
history, not part of the install.

Related: [[context]], [[upgrade]], [[compatibility]], [[development]].
