# crayon

crayon helps you draft documentation with your coding agent. You say what content you
need and where the facts are. crayon asks you questions, creates a plan and waits for
your approval before drafting the page and performing an initial review.

crayon can produce four types of Sphinx-ready drafts (MyST Markdown or reStructuredText),
corresponding to the four Diátaxis categories: tutorial, how-to, reference, and explanation.
crayon doesn't know your Sphinx theme, extensions or `conf.py`, and it never builds. It learns
your conventions from your existing docs, through `/crayon-onboard` and `/crayon-fetch`.

You use crayon through five skills in your coding agent.

## Requirements

- Python 3.9 or newer, available as `python3`.
- Git - Your docs repository must have a git user name and email set.
- A coding agent that can use Agent Skills (`SKILL.md` files) and run shell commands.

## Install

Run these commands in a terminal.

1. Download crayon:

   ```bash
   git clone https://github.com/canonical/crayon ~/src/crayon
   ```

2. Install the `crayon` tool used by the skills:

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

3. Go to your docs repository and copy the skills into it:

   ```bash
   cd /path/to/your-docs-repo
   mkdir -p .agents/skills && cp -r ~/src/crayon/skills/crayon-* .agents/skills/
   ```

4. Some agents read skills only from `.claude/skills/`. You can link the skills there too:

   ```bash
   mkdir -p .claude/skills
   (cd .claude/skills && ln -sf ../../.agents/skills/crayon-* .)
   ```

5. Tell git to ignore the folder where crayon keeps unfinished drafts:

   ```bash
   echo '.crayon/staging/' >> .gitignore
   ```

**Or use the installer.** After step 1, you can also run the installer instead of steps 2–5.
You'll need to verify the scope of the installation - project or global, the location of the
docs repository, and where the crayon executable should be installed.

```bash
cd /path/to/your-docs-repo
~/src/crayon/install.sh
```

For global skills, other folders and uninstalling, see [`docs/install.md`](docs/install.md).

## Use

Open your coding agent in the docs repository. Run the skills in this order:

1. `/crayon-onboard`: Run once per repository, optional. It reads your existing docs and code, and
   records your style, terms, and structure. These will guide the other skills.
2. `/crayon-plan`: Helps you define the requirements for the page you need by asking you a series
   of questions. Approve the final plan to move to the drafting stage.
3. `/crayon-write`: this skill drafts the page. For action-oriented docs, i.e., tutorials and how-tos,
   it runs each step first and creates drafts based on the actual output.
4. `/crayon-review`: Reads the draft and identifies errors/issues. You can accept the draft as-is, say
   what to fix, or ask for a new draft. For fixes or a new draft, you'll need to run `/crayon-write`
   again.

The accepted draft is saved under `docs/`. Each of the four steps is a local git commit. crayon also never pushes changes; you must open the pull request.

If your style guide, glossary, or other useful context is outside the repository, for example at a URL,
run `/crayon-fetch` and give it the location.

If you stop in the middle, run the same skill again. It finds where you stopped and continues.

## Use a separate branch

crayon's commits also store a record of how the page was made. It's cleaner to keep that record off your
main branch:

1. Before you start, create a branch for crayon, for example `git switch -c crayon/my-page`.
2. When the page is accepted, create a new branch from `main`. Copy only the page file to it,
   commit it and open the pull request from that branch.
3. Do not merge or delete the crayon branch. It keeps the full record of the page.

For the commands and the reasons, see
[Branches and the record](docs/internals.md#branches-and-the-record).

## What stays yours

crayon drafts and keeps the record. These decisions are yours:

- **Audience.** Who the page is for and where they arrive from. crayon asks; it doesn't choose.
- **Scope.** What the page covers and what it leaves out. crayon drafts nothing until you
  approve the plan.
- **Accept.** Whether the draft is good enough. You accept it, ask for a fix or ask for a new
  draft.
- **Publish.** crayon stops at a local commit. You open the pull request, build and merge.
  crayon doesn't label the page as AI-generated; the people who review and merge the page own it.

The record shows what was decided and in what order. It can't prove who decided: your
coding agent runs the commands that approve the plan and accept the draft, so the record can't
tell your yes from the agent's. Your accept in `/crayon-review` is your own judgment. The person
who reviews the pull request before it merges is the gate.

If you're not a technical author, ask one to review the page before you merge it.

## Optional code-to-docs mapping

`/crayon-plan` can perform a live crawl of the code to extract information relevant to a draft. This
approach doesn't create any lasting artifacts, but may have limited capacity in a large code base.

An alternative approach is to have a `code-to-docs-map.md` file in the same `context` folder that holds
the artifacts produced by the `/crayon-onboard` skill. The map is supposed to guide the skills towards
the relevant parts of the code while filtering out the unnecessary parts. Use the script provided in
the [Code to docs mapper](https://launchpad.net/code-to-docs-mapper). **Note** that this requires
a [Chromadb vector database](https://launchpad.net/wide-scope-rag) with separate collections for your
code and existing docs.

## Documentation

[`docs/contents.md`](docs/contents.md) lists every document, including how crayon works under
the hood.

## License

The tool is licensed under LGPL-3.0-only ([`LICENSE`](LICENSE)). The skills in
[`skills/`](skills/) are licensed under Apache-2.0 ([`skills/LICENSE`](skills/LICENSE)).
