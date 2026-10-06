# Upgrading dogen

<!-- provenance: rewritten as a forward-looking procedure; the previous page was a before/after of one release -->

How to move a machine, a repository and its records from one dogen release to the next. What
changed in a given release is in `CHANGELOG.md`. This page is the procedure.

## 1. Upgrade the tool

The tool is one file. Pull the checkout and run the installer again. It replaces the copy on
your `PATH` and checks it:

```bash
cd ~/src/dogen && git pull
./install.sh --yes            # or ./install.sh, to change any choice
```

If you installed with `--link`, the symlink already points to the new file. Run
`./install.sh --verify-only` to check that the tool and the skills still match.

## 2. Copy the skills again

The skills are copies, not links, so an upgrade must reach every place where you installed
them:

- **in a docs repository**: run `~/src/dogen/install.sh` in every repository you document (or
  repeat the manual copy in [[install]]), and commit the new copy so that your collaborators get
  it too;
- **for your user**: run `./install.sh --skills global` once.

Remove any old real copy of a skill in another skills folder: `.claude/skills/` (the
installer's own symlinks there are fine), `.github/skills/` or `.opencode/skills/`. An agent may
find the old copy first and run old instructions against the new tool. The installer's checks
warn when they see one.

## 3. Check that the skills and the tool match

Run `./install.sh --verify-only` in the checkout. It compares the contract number of the tool
with the one each skill was written for. A skill stops only when the contract numbers differ or
the tool is older than the skill needs. The current numbers are in [[compatibility]].

## 4. When the contract number changes

Within one contract number, a newer tool reads every record an older one wrote.

When the contract number changes, the new tool refuses records written under the old one. There
is no migration, by design: the record is append-only, and rewriting it would forge it. To
continue work on such a page:

1. Move the unit's record aside, for example
   `git mv .dogen/units/<id> .dogen/archive/<id>`. The old record stays readable as history.
2. Run `/dogen-plan` for the same page again. The page already exists, so the plan hands you to
   `/dogen-review`, which asks whether to record the current page as the starting point.

## 5. What never changes across upgrades

- **Your git history.** Nothing rewrites, moves or deletes a commit you already have.
- **The docs root.** Pages are written under `docs/`.
- **The approval gate.** dogen does not draft a page without your approval of the current
  plan.
- **The install shape.** One file on your `PATH` and five skill folders. No package, no virtual
  environment, no dependencies.

## Under the hood

`dogen version --json` answers `{"tool", "contract"}`. Each skill declares `dogen_contract`
and `dogen_min_tool` in its frontmatter; both are compared as literal strings.

Within one `contract` number, new event kinds are ignored for derivation with one warning, and
nothing state-affecting is added without a new contract number ([[contract]] §5.10). Records
written under another contract are **refused on every verb, read-only ones included**
(`ledger_version_unsupported`, exit 6), with a hint naming both numbers. There is no migration
command and no `--migrate` flag: a ledger is hash-chained and append-only. After the record is
moved aside, `dogen-plan` declares the unit again with `dogen unit new`, pointing at the page
that is already on disk. The tool reports `target_exists`, `dogen-plan` hands off to
`dogen-review`, and `dogen-review` adopts the current bytes as the new basis with `dogen edits`.

Two more invariants hold across releases: the shape of `unit.md` (frontmatter `title`,
`intent`, `audience`, `targets`, optional `sources` and `notes`, over a free-Markdown body), and
the gate itself (`signoff` freezes the sha256 of `unit.md`, and a draft with no current signoff
or against a stale plan hash is refused).

Related: [[install]], [[compatibility]], [[contract]], [[internals]].
