# dogen

dogen helps you write documentation with your coding agent. You say what page you need and
where the facts are. dogen asks you questions, writes a plan and waits for your approval. Then
it drafts the page, and you review it.

The page is ready for Sphinx: MyST Markdown or reStructuredText. Each page is one Diátaxis
type: tutorial, how-to, reference or explanation.

You use dogen through five skills in your coding agent. The skills do the rest.

## Requirements

- Python 3.9 or newer, available as `python3`.
- git. Your docs repository must have a git user name and email set.
- A coding agent that can use Agent Skills (`SKILL.md` files) and run shell commands.

## Install

Run these commands in a terminal.

1. Download dogen:

   ```bash
   git clone https://github.com/canonical/dogen ~/src/dogen
   ```

2. Install the `dogen` tool. The skills use it.

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

3. Go to your docs repository and copy the skills into it:

   ```bash
   cd /path/to/your-docs-repo
   mkdir -p .agents/skills && cp -r ~/src/dogen/skills/dogen-* .agents/skills/
   ```

4. Some agents read skills only from `.claude/skills/`. Link the skills there too:

   ```bash
   mkdir -p .claude/skills
   (cd .claude/skills && ln -sf ../../.agents/skills/dogen-* .)
   ```

5. Tell git to ignore the folder where dogen keeps unfinished drafts:

   ```bash
   echo '.dogen/staging/' >> .gitignore
   ```

**Or use the installer.** After step 1, you can run the installer instead of steps 2–5. It
asks where to put each part, checks the result and prints the commands to uninstall:

```bash
cd /path/to/your-docs-repo
~/src/dogen/install.sh
```

For global skills, other folders and uninstalling, see [`docs/install.md`](docs/install.md).

## Use

Open your coding agent in the docs repository. Run the skills in this order:

1. `/dogen-onboard`: once per repository, optional. It reads your existing docs and records
   your style, terms and structure. The other skills follow them.
2. `/dogen-plan`: describe the page you need. Answer the questions. Approve the plan.
3. `/dogen-write`: the skill drafts the page. For a tutorial or a how-to, it runs each step
   first and writes from the real output.
4. `/dogen-review`: read the draft. Accept it, say what to fix, or ask for a new draft. A fix or
   a new draft goes back to `/dogen-write`.

The page is saved under `docs/`. Each step is a local git commit. dogen never pushes; you open
the pull request.

If your style guide or glossary is outside the repository, for example at a URL, run
`/dogen-fetch` and give it the location.

If you stop in the middle, run the same skill again. It finds where you stopped and continues.

## Use a separate branch

dogen's commits also store a record of how the page was made. Keep that record off your main
branch:

1. Before you start, create a branch for dogen, for example `git switch -c dogen/my-page`.
2. When the page is accepted, create a new branch from `main`. Copy only the page file to it,
   commit it and open the pull request from that branch.
3. Do not merge or delete the dogen branch. It keeps the full record of the page.

For the commands and the reasons, see
[Branches and the record](docs/internals.md#branches-and-the-record).

## What dogen does not do

- It does not push, open pull requests, build or publish.
- It does not draft a page until you approve the plan.
- It does not label the page as AI-generated. The people who review and merge the page own it.
- It does not know your Sphinx theme, extensions or `conf.py`, and it never builds. It learns
  your conventions from your existing docs, through `/dogen-onboard` and `/dogen-fetch`.

## Documentation

[`docs/contents.md`](docs/contents.md) lists every document, including how dogen works under
the hood.

## License

The tool is licensed under LGPL-3.0-only ([`LICENSE`](LICENSE)). The skills in
[`skills/`](skills/) are licensed under Apache-2.0 ([`skills/LICENSE`](skills/LICENSE)).
