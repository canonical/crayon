# dogen

dogen helps you draft documentation with your coding agent. You say what content you
need and where the facts are. dogen asks you questions, creates a plan and waits for
your approval before drafting the page and performing an initial review.

dogen can produce four types of Sphinx-ready drafts (MyST Markdown or reStructuredText),
corresponding to the four Diátaxis categories: tutorial, how-to, reference, and explanation.

You use dogen through five skills in your coding agent.

## Requirements

- Python 3.9 or newer, available as `python3`.
- Git - Your docs repository must have a git user name and email set.
- A coding agent that can use Agent Skills (`SKILL.md` files) and run shell commands.

## Install

Run these commands in a terminal.

1. Download dogen:

   ```bash
   git clone https://github.com/canonical/dogen ~/src/dogen
   ```

2. Install the `dogen` tool used by the skills:

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

4. Some agents read skills only from `.claude/skills/`. You can link the skills there too:

   ```bash
   mkdir -p .claude/skills
   (cd .claude/skills && ln -sf ../../.agents/skills/dogen-* .)
   ```

5. Tell git to ignore the folder where dogen keeps unfinished drafts:

   ```bash
   echo '.dogen/staging/' >> .gitignore
   ```

**Or use the installer.** After step 1, you can also run the installer instead of steps 2–5.
You'll need to verify the scope of the installation - project or global, the location of the
docs repository, and where the dogen executable should be installed.

```bash
cd /path/to/your-docs-repo
~/src/dogen/install.sh
```

For global skills, other folders and uninstalling, see [`docs/install.md`](docs/install.md).

## Use

Open your coding agent in the docs repository. Run the skills in this order:

1. `/dogen-onboard`: Run once per repository, optional. It reads your existing docs and code, and
   records your style, terms, and structure. These will guide the other skills.
2. `/dogen-plan`: Helps you define the requirements for the page you need by asking you a series
   of questions. Approve the final plan to move to the drafting stage.
3. `/dogen-write`: this skill drafts the page. For action-oriented docs, i.e., tutorials and how-tos,
   it runs each step first and creates drafts based on the actual output.
4. `/dogen-review`: Reads the draft and identifies errors/issues. You can accept the draft as-is, say
   what to fix, or ask for a new draft. For fixes or a new draft, you'll need to run `/dogen-write`
   again.

The accepted draft is saved under `docs/`. Each of the four steps is a local git commit. dogen also never pushes changes; you must open the pull request.

If your style guide, glossary, or other useful context is outside the repository, for example at a URL,
run `/dogen-fetch` and give it the location.

If you stop in the middle, run the same skill again. It finds where you stopped and continues.

## Use a separate branch

dogen's commits also store a record of how the page was made. It's cleaner to keep that record off your
main branch:

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

## Optional code-to-docs mapping

`/dogen-plan` can perform a live crawl of the code to extract information relevant to a draft. This
approach doesn't create any lasting artifacts, but may have limited capacity in a large code base.

An alternative approach is to have a `code-to-docs-map.md` file in the same `context` folder that holds
the artifacts produced by the `/dogen-onboard` skill. The map is supposed to guide the skills towards
the relevant parts of the code while filtering out the unnecessary parts. Use the script provided in
the [Code to docs mapper](https://launchpad.net/code-to-docs-mapper). **Note** that this requires
a [Chromadb vector database](https://launchpad.net/wide-scope-rag) with separate collections for your
code and existing docs.

## Documentation

[`docs/contents.md`](docs/contents.md) lists every document, including how dogen works under
the hood.

## License

The tool is licensed under LGPL-3.0-only ([`LICENSE`](LICENSE)). The skills in
[`skills/`](skills/) are licensed under Apache-2.0 ([`skills/LICENSE`](skills/LICENSE)).
