#!/usr/bin/env bash
# install_smoke.sh — CI-02 / A-37: a stranger installs crayon and reaches a page.
#
# Usage: bash tests/install_smoke.sh   (run from anywhere; paths resolve from $0)
#
# The boundary, stated once: this script is the ONLY test that reaches `crayon`
# through PATH rather than through the in-tree `./crayon` file. It therefore does
# NOT source `tests/lib.sh` — that file pins `CRAYON="$REPO_ROOT/crayon.py"` and its
# `setup_repo` exports `CRAYON_TEST_HOOKS=1`, and either one would let a broken
# install pass as green (RESEARCH Pitfall 4). The guards worth copying from
# `tests/lib.sh:176-198` — the three-check `mktemp -d` and the pinned git config
# — are copied below; nothing else is.
#
# What it proves (D-09, D-10): the shell inside docs/install.md's
# `<!-- INSTALL:BEGIN -->` / `<!-- INSTALL:END -->` region — the documented
# scripted install, `install.sh --yes` — is extracted BYTE-IDENTICALLY — never
# sed'd, never templated — and executed from a temp HOME with a temp PATH in a
# hermetic temp repo. The smoke then drives one unit through the installed tool
# to a written page that `verify` and `show` both agree exists, and to a refusal
# that still carries the contract's five-key JSON shape. The guide's own
# `${CRAYON_SRC:-…}` and `${REPO:-$PWD}` defaults are what make that an override
# rather than a rewrite. The repository seed (git init, identity, a source and a
# docs root) is the smoke's own: the installer never initialises a repository.
#
# Exit codes follow the project's 0/1/2 lint contract:
#   0  the walk reached a page and every assertion passed
#   1  at least one assertion failed
#   2  NOTHING was checked — zero fenced bash blocks were extracted from the
#      marked region, or zero assertions were recorded. A smoke that ran nothing
#      is a vacuous pass, and reporting it green is the one outcome this script
#      must never produce.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

README="$REPO_ROOT/docs/install.md"
BEGIN_MARKER='<!-- INSTALL:BEGIN -->'
END_MARKER='<!-- INSTALL:END -->'
UNIT="widget-api"

# Pitfall 6 / assumption A2: pinned OUTSIDE the extracted region, so a
# runner-side or developer-side global identity can never mask a missing
# `git config` step INSIDE the region. The region must carry its own identity.
export GIT_CONFIG_GLOBAL=/dev/null
export GIT_CONFIG_SYSTEM=/dev/null

assertions=0
failures=0
SMOKE_HOME=""
SMOKE_REPO=""

cleanup() {
    if [ -n "$SMOKE_HOME" ] && [ -d "$SMOKE_HOME" ]; then
        rm -rf "$SMOKE_HOME"
    fi
    if [ -n "$SMOKE_REPO" ] && [ -d "$SMOKE_REPO" ]; then
        rm -rf "$SMOKE_REPO"
    fi
    return 0
}
trap cleanup EXIT

# Every assertion prints its own one-line description, so a red CI run names
# which one failed without anyone reading the script.
pass() {
    assertions=$((assertions + 1))
    printf 'ok   — %s\n' "$1"
}

fail() {
    assertions=$((assertions + 1))
    failures=$((failures + 1))
    printf 'FAIL — %s\n' "$1" >&2
}

assert_eq() {
    if [ "$2" = "$3" ]; then
        pass "$1"
    else
        fail "$1 (expected [$2], got [$3])"
    fi
}

# --- hermetic temp tree ------------------------------------------------------
# WR-08: `cd ""` SUCCEEDS in bash and leaves the shell where it is, so
# `cd "$X" || exit 1` is not a guard on its own. With an unchecked `mktemp -d`
# — a full or read-only /tmp, a restrictive TMPDIR — the walk below would
# `git init`, write `docs/index.md` and commit in the CURRENT directory, which
# is the crayon repository. The three checks make the failure loud instead.
SMOKE_HOME=$(mktemp -d) || exit 1
[ -n "$SMOKE_HOME" ] && [ -d "$SMOKE_HOME" ] || exit 1
SMOKE_REPO=$(mktemp -d) || exit 1
[ -n "$SMOKE_REPO" ] && [ -d "$SMOKE_REPO" ] || exit 1

# --- extract the marked region ----------------------------------------------
# Byte-identical (D-10): awk prints the fence bodies unchanged and inserts only
# comment lines BETWEEN them, so the concatenation is the README's own bytes.
EXTRACTED="$SMOKE_HOME/quickstart.sh"
awk -v begin_marker="$BEGIN_MARKER" -v end_marker="$END_MARKER" '
    index($0, begin_marker) { region = 1; next }
    index($0, end_marker)   { region = 0; next }
    region != 1             { next }
    fence == 1 && /^```/    { fence = 0; next }
    fence == 1              { print; next }
    /^```bash *$/           { n += 1; print "# --- install fence " n " ---"; fence = 1 }
' "$README" >"$EXTRACTED"

FENCES=$(grep -c '^# --- install fence ' "$EXTRACTED" 2>/dev/null) || FENCES=0

# The `2` arm, half one: nothing was extracted, so nothing can be run. Name
# what was searched — the same courtesy `run_matrix.sh` extends when its own
# vacuous-pass guard fires.
if [ "$FENCES" -eq 0 ]; then
    echo "install-smoke: ERROR - extracted 0 fenced bash blocks (vacuous pass guard)" >&2
    echo "install-smoke:   searched: $README" >&2
    echo "install-smoke:   between:  $BEGIN_MARKER" >&2
    echo "install-smoke:   and:      $END_MARKER" >&2
    exit 2
fi

# --- the PATH premise (T-18-07) ----------------------------------------------
# A developer with crayon already installed globally would sail through this
# whole script without the region's install step doing anything at all. Strip
# any ambient entry from this script's OWN PATH — loudly, naming the path it
# resolved to — so the only `crayon` the extracted script can reach is the one
# it copies itself.
strip_path_entry() {
    local drop="$1" rebuilt="" entry resolved
    while IFS= read -r entry; do
        [ -n "$entry" ] || continue
        if [ "$entry" = "$drop" ]; then
            continue
        fi
        resolved=$(cd "$entry" 2>/dev/null && pwd) || resolved=""
        if [ -n "$resolved" ] && [ "$resolved" = "$drop" ]; then
            continue
        fi
        rebuilt="${rebuilt:+$rebuilt:}$entry"
    done <<<"${PATH//:/$'\n'}"
    printf '%s' "$rebuilt"
}

ambient=$(command -v crayon 2>/dev/null) || ambient=""
strips=0
while [ -n "$ambient" ] && [ "$strips" -lt 8 ]; do
    ambient_dir=$(cd "$(dirname "$ambient")" && pwd)
    echo "install-smoke: note - dropping ambient crayon from PATH: $ambient" >&2
    PATH=$(strip_path_entry "$ambient_dir")
    export PATH
    strips=$((strips + 1))
    ambient=$(command -v crayon 2>/dev/null) || ambient=""
done
assert_eq "a37: no ambient crayon is reachable before the install step runs" \
    "" "$ambient"

# --- seed the stranger's repository ------------------------------------------
# The installer requires a git repository and refuses to create one, so the
# smoke seeds it: a repo-local identity (the global one is /dev/null above), a
# source file and a docs root, committed, and NO .gitignore — the installer's
# own gitignore step is asserted below.
(
    cd "$SMOKE_REPO" \
        && git init -q -b main . \
        && git config user.name "Anne Example" \
        && git config user.email "anne@example.com" \
        && printf '# Widget API\n\nCreate and delete widgets.\n' >source.md \
        && mkdir -p docs \
        && printf '# Docs\n' >docs/index.md \
        && git add -A \
        && git commit -q -m "seed the docs repo"
) || exit 1

# `.claude` is often a symlink into a dotfiles checkout; the compat links the
# installer writes under it must resolve from where they physically live.
mkdir -p "$SMOKE_HOME/dotfiles/claude" && ln -s "$SMOKE_HOME/dotfiles/claude" "$SMOKE_REPO/.claude"

# --- run the region exactly as written --------------------------------------
# The two guide defaults are overridden from the environment, never in the
# bytes. HOME is redirected into the temp tree so the region's documented
# `~/.local/bin` install lands inside this smoke and nowhere else.
echo "── running $FENCES fenced block(s) from the INSTALL region ──"
INSTALL_OUT="$SMOKE_HOME/install.out"
if HOME="$SMOKE_HOME" CRAYON_SRC="$REPO_ROOT" REPO="$SMOKE_REPO" \
        bash -euo pipefail "$EXTRACTED" >"$INSTALL_OUT" 2>&1; then
    pass "a37: the INSTALL region ran end to end under set -euo pipefail"
else
    fail "a37: the INSTALL region exited non-zero"
fi
cat "$INSTALL_OUT"

# The installer put the tool in its own HOME; reach it the same way it did.
SMOKE_BIN="$SMOKE_HOME/.local/bin"
export PATH="$SMOKE_BIN:$PATH"

resolved_crayon=$(command -v crayon 2>/dev/null) || resolved_crayon=""
assert_eq "a37: the installed crayon resolves inside the smoke's temp bin" \
    "$SMOKE_BIN/crayon" "$resolved_crayon"
case "$resolved_crayon" in
    "$REPO_ROOT"/*)
        fail "a37: the resolved crayon is the in-tree file, not the installed copy ($resolved_crayon)"
        ;;
    *)
        pass "a37: the resolved crayon is outside the crayon checkout"
        ;;
esac

# --- what the installer placed -----------------------------------------------
for skill in crayon-onboard crayon-fetch crayon-plan crayon-write crayon-review; do
    if [ -f "$SMOKE_REPO/.agents/skills/$skill/SKILL.md" ] \
        && [ -f "$SMOKE_REPO/.agents/skills/$skill/references/routing.md" ]; then
        pass "a37: the installer placed $skill under the repo's .agents/skills/"
    else
        fail "a37: $skill is missing or incomplete under $SMOKE_REPO/.agents/skills/"
    fi
done
for skill in crayon-onboard crayon-fetch crayon-plan crayon-write crayon-review; do
    link="$SMOKE_REPO/.claude/skills/$skill"
    if [ -L "$link" ] && [ -f "$link/SKILL.md" ]; then
        pass "a37: the installer linked $skill from .claude/skills/"
    else
        fail "a37: $link is not a symlink to the installed skill"
    fi
done
if [ -f "$SMOKE_REPO/.agents/skills/README.md" ]; then
    fail "a37: the installer copied skills/README.md, which is not a skill"
else
    pass "a37: the installer copied the five skills and nothing else"
fi
if grep -qxF '.crayon/staging/' "$SMOKE_REPO/.gitignore" 2>/dev/null; then
    pass "a37: the installer added .crayon/staging/ to .gitignore"
else
    fail "a37: .crayon/staging/ is not in $SMOKE_REPO/.gitignore"
fi
verify_only_exit=0
HOME="$SMOKE_HOME" bash "$REPO_ROOT/install.sh" --verify-only --yes \
    --repo "$SMOKE_REPO" --tool-dir "$SMOKE_BIN" >/dev/null 2>&1 || verify_only_exit=$?
assert_eq "a37: install.sh --verify-only passes over the installed tree" \
    "0" "$verify_only_exit"

# --- one unit through the installed tool -------------------------------------
# The walk the guide used to carry; it lives here now so the guide stays what a
# reader runs. `steer` is load-bearing: without it, `draft` refuses `unsteered`.
walk_exit=0
(
    cd "$SMOKE_REPO" \
        && printf '# Plan\n\nOutline the widget API reference.\n' \
            | crayon unit new "$UNIT" \
                --intent reference \
                --audience "developers integrating the widget API" \
                --title "Widget API" \
                --target "reference/$UNIT.md" \
                --source source.md \
                --body-file - \
        && crayon signoff "$UNIT" \
        && crayon steer "$UNIT" --note "Lead with the create call." \
        && mkdir -p ".crayon/staging/$UNIT/draft" \
        && printf '# Widget API\n\n## create\n\nCreates a widget.\n' \
            >".crayon/staging/$UNIT/draft/$UNIT.md" \
        && crayon draft "$UNIT" ".crayon/staging/$UNIT/draft/$UNIT.md"
) >/dev/null 2>&1 || walk_exit=$?
assert_eq "a37: declare, signoff, steer and draft run through the installed crayon" \
    "0" "$walk_exit"

# --- the context verbs through the installed tool ----------------------------
# What /crayon-onboard and /crayon-fetch do: hand the tool an artefact's text, then
# record the set. Repo-level, no unit, one commit.
context_exit=0
(
    cd "$SMOKE_REPO" \
        && printf '# Style\n\nImperative mood.\n' \
            | crayon context stage doc-style.md --body-file - --source source.md \
        && crayon context record --note "smoke: one artefact"
) >/dev/null 2>&1 || context_exit=$?
assert_eq "a37: context stage and record run through the installed crayon" \
    "0" "$context_exit"
if [ -s "$SMOKE_REPO/.crayon/context/doc-style.md" ] \
    && [ -s "$SMOKE_REPO/.crayon/context/manifest.json" ]; then
    pass "a37: the record placed the artefact and its manifest under .crayon/context/"
else
    fail "a37: .crayon/context/ lacks the artefact or the manifest after the record"
fi

# --- assert from the stranger's vantage point -------------------------------
PAGE="$SMOKE_REPO/docs/reference/$UNIT.md"
if [ -s "$PAGE" ]; then
    pass "a37: the walk wrote a non-empty page at docs/reference/$UNIT.md"
else
    fail "a37: no non-empty page at $PAGE"
fi

verify_json=$(cd "$SMOKE_REPO" && crayon verify "$UNIT" --json 2>/dev/null)
verify_exit=$?
assert_eq "a37: crayon verify exits 0 over the installed walk" "0" "$verify_exit"
verify_verdict=$(printf '%s' "$verify_json" | python3 -c '
import json, sys
try:
    print(json.load(sys.stdin)["verdict"])
except Exception:
    print("UNPARSEABLE")
')
assert_eq "a37: crayon verify --json reports verdict ok" "ok" "$verify_verdict"

show_shape=$(cd "$SMOKE_REPO" && crayon show "$UNIT" --json 2>/dev/null | python3 -c '
import json, sys
try:
    payload = json.load(sys.stdin)
except Exception:
    print("UNPARSEABLE")
    sys.exit(0)
paths = payload.get("paths") or []
print("%s/%d" % (payload.get("state"), len(paths)))
')
assert_eq "a37: crayon show --json reports a drafted state and one path" \
    "drafted/1" "$show_shape"

# --- the refusal surface survives a PATH install (GATE-04) -------------------
# A second generation with nothing recorded since the last one refuses
# `unsteered`: exit 1, exactly one line on stderr, and that line the contract's
# five-key JSON object. Proving that from the stranger's vantage point is what
# separates "a tool ran" from "the real tool ran".
STAGED="$SMOKE_REPO/.crayon/staging/$UNIT/draft/$UNIT.md"
REFUSAL_ERR="$SMOKE_HOME/refusal.err"
printf '# Widget API\n\n## create\n\nCreates a widget. Second pass.\n' >"$STAGED"
refusal_exit=0
(cd "$SMOKE_REPO" && crayon draft "$UNIT" ".crayon/staging/$UNIT/draft/$UNIT.md") \
    >/dev/null 2>"$REFUSAL_ERR" || refusal_exit=$?
assert_eq "a37: an unsteered second draft refuses with exit 1 (GATE-04)" \
    "1" "$refusal_exit"
refusal_lines=$(wc -l <"$REFUSAL_ERR" | tr -d ' ')
assert_eq "a37: the refusal writes exactly one line to stderr (GATE-04)" \
    "1" "$refusal_lines"
refusal_error=$(python3 -c '
import json, sys
try:
    payload = json.loads(open(sys.argv[1], encoding="utf-8").read())
except Exception:
    print("UNPARSEABLE")
    sys.exit(0)
missing = [k for k in ("error", "unit", "detail", "hint", "next") if k not in payload]
print("MISSING:" + ",".join(missing) if missing else payload["error"])
' "$REFUSAL_ERR")
assert_eq "a37: the refusal line is the five-key JSON object for unsteered" \
    "unsteered" "$refusal_error"

# --- the uninstall the installer printed --------------------------------------
# The installer ends by printing the commands that remove what it placed, with
# the paths it used. Run exactly those lines — never a list kept here — and
# check that the tool, the five skills and their links are gone, while the
# record the walk committed stays.
UNINSTALL="$SMOKE_HOME/uninstall.sh"
sed -n '/^To uninstall, run:$/,/^[^ ]/p' "$INSTALL_OUT" | grep '^  rm ' >"$UNINSTALL" || true
uninstall_lines=$(wc -l <"$UNINSTALL" | tr -d ' ')
assert_eq "a37: the installer printed one rm line for the tool, each skill and each link" \
    "11" "$uninstall_lines"
if grep -qxF "Then delete the line .crayon/staging/ from $SMOKE_REPO/.gitignore." "$INSTALL_OUT"; then
    pass "a37: the installer named the .gitignore line to delete"
else
    fail "a37: the installer did not name the .gitignore line to delete"
fi
uninstall_exit=0
bash -eu "$UNINSTALL" >/dev/null 2>&1 || uninstall_exit=$?
assert_eq "a37: the printed uninstall commands run cleanly" "0" "$uninstall_exit"
left=""
[ -e "$SMOKE_BIN/crayon" ] && left="$left $SMOKE_BIN/crayon"
for skill in crayon-onboard crayon-fetch crayon-plan crayon-write crayon-review; do
    [ -e "$SMOKE_REPO/.agents/skills/$skill" ] && left="$left .agents/skills/$skill"
    [ -L "$SMOKE_REPO/.claude/skills/$skill" ] && left="$left .claude/skills/$skill"
done
assert_eq "a37: nothing the installer placed is left after the uninstall" "" "$left"
if [ -d "$SMOKE_REPO/.crayon/units/$UNIT" ]; then
    pass "a37: the uninstall left the record under .crayon/ in place"
else
    fail "a37: the record under .crayon/units/$UNIT is gone after the uninstall"
fi

# --- report ------------------------------------------------------------------
echo ""
echo "install-smoke: $FENCES fenced block(s) ran, $assertions assertion(s), $failures failed"

# The `2` arm, half two: a run that recorded no assertion proved nothing, even
# if every command in it happened to exit 0.
if [ "$assertions" -eq 0 ]; then
    echo "install-smoke: ERROR - recorded 0 assertions (vacuous pass guard)" >&2
    exit 2
fi
if [ "$failures" -ne 0 ]; then
    exit 1
fi
exit 0
