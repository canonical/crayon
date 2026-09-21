# Compatibility

<!-- provenance: moved from README.md (Compatibility); the numbers are contract 5.10 -->

Two numbers decide whether a skill and a tool may work together. Their home is [[contract]]
§5.10; this page states them for a reader and
is checked against the tool by `tests/check_docs.py`.

<!-- COMPAT:BEGIN -->

| Number | Value |
|---|---|
| `contract` | `1` |
| `min_tool` | `0.2.0` |

`dogen version --json` reports both. A skill stops on exactly two conditions: a `contract`
number that is not the one it was written against, or a tool older than `min_tool`. Nothing
else about a version is checked, and the two numbers are compared as literal strings — never
parsed or rounded as versions.

<!-- COMPAT:END -->

Every skill declares the pair in its frontmatter as `metadata.dogen_contract` and
`metadata.dogen_min_tool`, and opens by reading `dogen version --json`. `install.sh` makes the
same comparison at the end of an install, so a mismatch is reported before a skill meets it.

## Records under another contract

A ledger whose header event carries a different `contract` is never half-read: every verb
refuses it, read-only ones included (`ledger_version_unsupported`, exit 6). Records are archived,
never migrated in place — see [[upgrade]].

Related: [[upgrade]], [[contract]], [[install]].
