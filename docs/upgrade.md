# Upgrading dogen

<!-- provenance: rewritten as a forward-looking procedure; the previous page was a before/after of one release -->

How to move a machine, a repository and its records from one dogen release to the next. The
normative rules are in [[contract]]; what changed in a given release is in `CHANGELOG.md`. This
page is the procedure.

## 1. Upgrade the executable

The tool is one file. Pull the checkout and re-run the installer, which replaces the copy on
your `PATH` and verifies it:

```bash
cd ~/src/dogen && git pull
./install.sh --yes            # or ./install.sh, to revisit any choice
```

If you installed with `--link`, the symlink already points at the pulled file; run
`./install.sh --verify-only` to confirm the pair of numbers below still agree.

## 2. Re-copy the skills

The skills are copied, not linked, so an upgrade must reach every place they were installed:

- **project-scoped** — re-run `./install.sh --repo <docs-repo>` in every repository you document
  (or the manual `cp -r` line in [[install]]), and commit the
  new copy so collaborators get it too;
- **global** — `./install.sh --skills global` once.

Remove any stale real copy under another discovery root — `.claude/skills/` (the installer's
own symlinks there are fine), `.github/skills/`, `.opencode/skills/` — because an agent may find it first and silently run old prose against the
new tool. The installer's verification warns when it sees one.

## 3. Check the two numbers

`dogen version --json` answers `{"tool", "contract"}`. Each skill declares `dogen_contract` and
`dogen_min_tool` in its frontmatter. A skill stops only when the contract numbers differ or the
tool is older than `min_tool`; both are compared as literal strings. `./install.sh --verify-only`
makes the comparison for you. The current values are in [[compatibility]].

## 4. What a contract bump means for existing records

Within one `contract` number, a newer tool reads every record an older one wrote: new event
kinds are ignored for derivation with one warning, and nothing state-affecting is added without
a new contract number ([[contract]] §5.10).

When the contract number changes, records written under the old one are **refused on every
verb, read-only ones included** (`ledger_version_unsupported`, exit 6), with a hint naming both
numbers. There is no migration command and no `--migrate` flag, by design: a ledger is
hash-chained and append-only, and a tool that rewrote one in place would be forging the record it
exists to keep. The policy is:

1. Move the unit directory aside (`git mv .dogen/units/<id> .dogen/archive/<id>`, or anywhere
   outside `.dogen/units/`). The old record stays readable as history.
2. Declare the unit again with `dogen unit new`, pointing at the page that already exists on
   disk; `dogen edits` adopts the current bytes as the new basis.

## 5. What never changes across upgrades

- **Your git history.** Nothing rewrites, moves or deletes a commit you already have.
- **The docs root.** Pages are written under `docs/`, and a target is a docs-relative path.
- **The shape of `unit.md`.** Frontmatter (`title`, `intent`, `audience`, `targets`, optional
  `sources` and `notes`) over a free-Markdown body.
- **The gate.** `signoff` freezes the sha256 of `unit.md`, and a draft with no current signoff or
  against a stale plan hash is refused.
- **The install shape.** A file on `PATH`, no package, no venv, no dependencies.

Related: [[install]], [[compatibility]], [[contract]].
