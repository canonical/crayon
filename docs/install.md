# Installing crayon

<!-- provenance: moved from README.md (Install and first run, Installing the skills globally, Add context files); reordered to put the manual install first -->

crayon has two parts:

- the `crayon` tool: one Python file, `crayon.py`, installed on your `PATH` as `crayon`;
- five Agent Skills: `crayon-onboard`, `crayon-fetch`, `crayon-plan`, `crayon-write` and
  `crayon-review`. Your agent runs them, and they use the tool.

To install crayon, put the tool on your `PATH` and the skills where your agent finds them. You
can do this by hand in a few commands, or run the installer, `install.sh`.

## Requirements

- Python 3.9 or newer, available as `python3`. Nothing else: no package, no virtual
  environment, no dependency.
- git. Your docs repository must have a git user name and email (`user.name` and
  `user.email`), because crayon makes a local commit for every step.
- A coding agent that can use Agent Skills (`SKILL.md` files) and run shell commands. Most
  agents find skills under `.agents/skills/`. Some read only `.claude/skills/`, so step 4 below
  links the skills there too. You run a skill by its name, for example `/crayon-plan`.

## Install by hand

1. Download crayon:

   ```bash
   git clone https://github.com/canonical/crayon ~/src/crayon
   ```

2. Install the tool:

   ```bash
   mkdir -p ~/.local/bin
   cp ~/src/crayon/crayon.py ~/.local/bin/crayon
   chmod +x ~/.local/bin/crayon
   ```

   Check it: `command -v crayon` must print a path. If it prints nothing, add this line to your
   shell profile (for example, `~/.bashrc`) and open a new terminal:

   ```bash
   export PATH="$HOME/.local/bin:$PATH"
   ```

3. Install the skills. Choose one place.

   In your docs repository (recommended). The skills travel with the repository, and your
   collaborators get the same version:

   ```bash
   cd /path/to/your-docs-repo
   mkdir -p .agents/skills && cp -r ~/src/crayon/skills/crayon-* .agents/skills/
   ```

   Or once for your user, so that every repository on this machine finds them:

   ```bash
   mkdir -p ~/.agents/skills && cp -r ~/src/crayon/skills/crayon-* ~/.agents/skills/
   ```

   `crayon-*` matches exactly the five skills. It does not copy `skills/README.md`, which is not
   a skill.

4. Link the skills from `.claude/skills/`, for the agents that read only that folder.

   In your docs repository:

   ```bash
   mkdir -p .claude/skills
   (cd .claude/skills && ln -sf ../../.agents/skills/crayon-* .)
   ```

   Or for your user:

   ```bash
   mkdir -p ~/.claude/skills
   ln -sf ~/.agents/skills/crayon-* ~/.claude/skills/
   ```

   If `.claude` in your docs repository is itself a symlink, use the installer instead. It
   computes links that work from where `.claude` really is.

5. In your docs repository, tell git to ignore the folder where crayon keeps unfinished drafts:

   ```bash
   echo '.crayon/staging/' >> .gitignore
   ```

6. If you installed the skills in the docs repository, commit `.agents/skills/`,
   `.claude/skills/` and `.gitignore`, so that your collaborators get them.

7. Check the install. Run this in your docs repository. It changes nothing:

   ```bash
   ~/src/crayon/install.sh --verify-only --yes
   ```

   For skills installed for your user, add `--skills global`.

## Install with the script

The installer does the same steps as the manual install. Run it from your docs repository:

```bash
cd /path/to/your-docs-repo
~/src/crayon/install.sh
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
  install again in each repository you document, and again after you upgrade crayon.
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
- **link**: a symlink from `~/.local/bin/crayon` to the file in your checkout. `git pull` in the
  checkout then upgrades the tool without a new install. The tool also changes whenever the
  checkout changes, so use a copy for a repository other people rely on.
- Any other folder of your own.

Flags: `--tool-dir DIR`, `--link`.

### 3. `.gitignore`

crayon keeps unfinished drafts under `.crayon/staging/`. This folder is working space and
belongs in the repository's `.gitignore`. For project skills, the script offers to add the
line. `--no-gitignore` declines. Without the line, crayon's checks report a warning.

### What the script checks

At the end, the script checks the install and prints one line per check:

- `python3` is 3.9 or newer;
- the `crayon` tool is where you asked, and the `crayon` found on your `PATH` is that file, not
  an older copy earlier on your `PATH`;
- the tool runs and reports its version and contract number, and the contract number is the one
  each installed skill was written for (`metadata.crayon_contract` in its `SKILL.md`, compared
  as a literal string);
- each skill folder holds its `SKILL.md` and `references/routing.md`;
- each link in `.claude/skills/` points to the installed skill;
- no old copy of a skill sits in another skills folder (`.claude/skills/`, `.github/skills/`,
  `.opencode/skills/`), where an agent may find it first;
- the repository has a git user name and email, and `.crayon/staging/` is ignored.

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
CRAYON_SRC="${CRAYON_SRC:-$HOME/src/crayon}"  # your checkout of crayon
REPO="${REPO:-$PWD}"                          # the docs repo you are documenting
```

```bash
export PATH="$HOME/.local/bin:$PATH"
bash "$CRAYON_SRC/install.sh" --yes --repo "$REPO" --tool-dir "$HOME/.local/bin"
```

<!-- INSTALL:END -->

## Add context files (recommended)

Context files teach the skills your house style, your terms and where facts live. To create
them, open your agent in the docs repository and run `/crayon-onboard`. It reads the docs you
already have.

If you already have a style guide or a glossary, run `/crayon-fetch` and give it the file path
or the URL. The five context files, and what `/crayon-plan` does when they are missing, are in
[[context]].

## Uninstall

The installer prints these commands with your exact paths. For the default places, they are:

```bash
rm -f ~/.local/bin/crayon
```

For skills in a docs repository, run this in the repository, then delete the line
`.crayon/staging/` from its `.gitignore`:

```bash
rm -rf .agents/skills/crayon-*
rm -f .claude/skills/crayon-*
```

For skills installed for your user:

```bash
rm -rf ~/.agents/skills/crayon-*
rm -f ~/.claude/skills/crayon-*
```

Uninstalling leaves your pages and the record under `.crayon/` in place. They are committed
history, not part of the install.

Related: [[context]], [[upgrade]], [[compatibility]], [[development]].
