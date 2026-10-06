#!/usr/bin/env bash
# install.sh — install dogen and its five skills, then verify the install.
#
# Usage:
#   ./install.sh                 walk through every decision; Enter takes the default
#   ./install.sh --yes           take every default without asking
#   ./install.sh --verify-only   check an existing install and report
#   ./install.sh --help          every flag
#
# Decisions, in order (each one is also a flag, so a script can answer it):
#   1. where the skills go       --skills project|global   [--repo DIR] [--skills-root DIR]
#   2. where the tool goes       --tool-dir DIR | --link
#   3. .gitignore                --no-gitignore
# The skills are also linked from .claude/skills/, the one discovery root some
# agents read instead of .agents/skills/; --no-compat-links skips that.
# Then the install is verified, and the commands that remove it are printed.
# Exit 0 when every check passed, 1 when one failed, 2 when nothing could be
# checked. The script never runs git init, git commit, sudo, or anything else
# that changes a repository's history.

set -u

# --- defaults ----------------------------------------------------------------
DOGEN_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS=""
REPO=""
SKILLS_ROOT=""
TOOL_DIR=""
LINK=0
GITIGNORE=1
COMPAT_LINKS=1
YES=0
VERIFY_ONLY=0
answer=""

DEFAULT_TOOL_DIR="$HOME/.local/bin"
GLOBAL_SKILLS_ROOT="$HOME/.agents/skills"
SKILL_NAMES="dogen-onboard dogen-fetch dogen-plan dogen-write dogen-review"

usage() {
    sed -n '2,19p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    cat <<'EOF'

Flags:
  --yes                 answer every prompt with its default
  --skills SCOPE        project (default) or global
  --repo DIR            the docs repository (project scope; default: the current directory)
  --skills-root DIR     the discovery root, when your agent does not read .agents/skills/
  --tool-dir DIR        where the dogen executable is copied (default: ~/.local/bin)
  --link                symlink the executable into the checkout instead of copying it
  --no-gitignore        do not add .dogen/staging/ to the repository's .gitignore
  --no-compat-links     do not link the skills from .claude/skills/ as well
  --dogen-src DIR       the dogen checkout to install from (default: this script's directory)
  --verify-only         change nothing; verify an existing install and report
  --help                this text
EOF
}

die() {
    printf 'install: error - %s\n' "$*" >&2
    exit 1
}

# --- flags -------------------------------------------------------------------
while [ $# -gt 0 ]; do
    case "$1" in
        --yes) YES=1 ;;
        --skills) shift; SKILLS="${1:-}" ;;
        --repo) shift; REPO="${1:-}" ;;
        --skills-root) shift; SKILLS_ROOT="${1:-}" ;;
        --tool-dir) shift; TOOL_DIR="${1:-}" ;;
        --link) LINK=1 ;;
        --no-gitignore) GITIGNORE=0 ;;
        --no-compat-links) COMPAT_LINKS=0 ;;
        --dogen-src) shift; DOGEN_SRC="${1:-}" ;;
        --verify-only) VERIFY_ONLY=1 ;;
        -h|--help) usage; exit 0 ;;
        *) die "unknown flag $1 (try --help)" ;;
    esac
    shift
done

[ -f "$DOGEN_SRC/dogen.py" ] || die "no dogen.py at $DOGEN_SRC (pass --dogen-src)"
[ -d "$DOGEN_SRC/skills/dogen-plan" ] || die "no skills under $DOGEN_SRC/skills"

# --- prompting ---------------------------------------------------------------
# ask VAR "question" "default": with --yes, or with no terminal, the default.
ask() {
    local var="$1" question="$2" default="$3" reply=""
    if [ "$YES" -eq 1 ] || [ ! -t 0 ]; then
        printf -v "$var" '%s' "$default"
        return 0
    fi
    printf '%s [%s]: ' "$question" "$default"
    IFS= read -r reply
    printf -v "$var" '%s' "${reply:-$default}"
}

say() { printf '%s\n' "$*"; }

# choose VAR "question" DEFAULT_INDEX "value|description"...: a numbered menu.
# The reply may be the option's number, its value word, or (when the last
# option's value is "other") any other text, taken verbatim. With --yes, or
# with no terminal, the default option's value.
choose() {
    local var="$1" question="$2" default="$3" reply="" i=1 opt value
    shift 3
    local -a values=() descs=()
    for opt in "$@"; do
        values+=("${opt%%|*}"); descs+=("${opt#*|}")
    done
    if [ "$YES" -eq 1 ] || [ ! -t 0 ]; then
        printf -v "$var" '%s' "${values[$((default - 1))]}"
        return 0
    fi
    printf '\n%s\n' "$question"
    for value in "${values[@]}"; do
        printf '  %d) %-16s %s\n' "$i" "$value" "${descs[$((i - 1))]}"
        i=$((i + 1))
    done
    printf '  choice [%d]: ' "$default"
    IFS= read -r reply
    reply="${reply:-$default}"
    if [[ "$reply" =~ ^[0-9]+$ ]] && [ "$reply" -ge 1 ] && [ "$reply" -le "${#values[@]}" ]; then
        printf -v "$var" '%s' "${values[$((reply - 1))]}"
        return 0
    fi
    for value in "${values[@]}"; do
        if [ "$reply" = "$value" ]; then
            printf -v "$var" '%s' "$value"
            return 0
        fi
    done
    if [ "${values[$((${#values[@]} - 1))]}" = "other" ]; then
        printf -v "$var" '%s' "$reply"
        return 0
    fi
    die "no such option: $reply"
}

# Prompt text is shown only when a prompt will follow it.
explain() {
    if [ "$YES" -eq 0 ] && [ -t 0 ]; then
        printf '%s\n' "$*"
    fi
}

# --- decision 1: skills scope ------------------------------------------------
if [ -z "$SKILLS" ]; then
    choose SKILLS "1/3  Where should the skills be installed?" 1 \
        "project|into the docs repository's .agents/skills/, so they travel with it" \
        "global|once, into ~/.agents/skills/, so every repository discovers them"
fi
case "$SKILLS" in
    project|global) ;;
    *) die "--skills must be project or global (got '$SKILLS')" ;;
esac

if [ "$SKILLS" = "project" ]; then
    if [ -z "$REPO" ]; then
        ask REPO "     the docs repository" "$PWD"
    fi
    REPO="$(cd "$REPO" 2>/dev/null && pwd)" || die "no such directory: $REPO"
    if ! git -C "$REPO" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        die "$REPO is not a git repository; dogen records into the repository it runs in — initialise one first (git init), then re-run"
    fi
    if [ -z "$SKILLS_ROOT" ]; then
        SKILLS_ROOT=".agents/skills"
    fi
    case "$SKILLS_ROOT" in
        /*) ;;
        *) SKILLS_ROOT="$REPO/$SKILLS_ROOT" ;;
    esac
else
    if [ -z "$SKILLS_ROOT" ]; then
        SKILLS_ROOT="$GLOBAL_SKILLS_ROOT"
    fi
fi

# --- decision 2: the tool ----------------------------------------------------
if [ "$LINK" -eq 0 ] && [ -z "$TOOL_DIR" ]; then
    choose TOOL_DIR "2/3  Where should the dogen executable go?" 1 \
        "$DEFAULT_TOOL_DIR|a copy; no sudo, the usual place for user tools" \
        "/usr/local/bin|a copy for every user; needs write access to that directory" \
        "link|a symlink into this checkout: git pull upgrades the tool" \
        "other|a directory of your own (or type the path directly)"
    if [ "$TOOL_DIR" = "link" ]; then
        LINK=1
        TOOL_DIR=""
    elif [ "$TOOL_DIR" = "other" ]; then
        ask TOOL_DIR "  directory" "$DEFAULT_TOOL_DIR"
    fi
fi
if [ "$LINK" -eq 1 ] && [ -z "$TOOL_DIR" ]; then
    TOOL_DIR="$DEFAULT_TOOL_DIR"
fi
case "$TOOL_DIR" in
    "~"*) TOOL_DIR="$HOME${TOOL_DIR#"~"}" ;;
esac

# --- decision 3: .gitignore --------------------------------------------------
if [ "$SKILLS" = "project" ] && [ "$GITIGNORE" -eq 1 ] && [ "$VERIFY_ONLY" -eq 0 ]; then
    if ! grep -qxF '.dogen/staging/' "$REPO/.gitignore" 2>/dev/null; then
        choose answer "3/3  dogen stages drafts under .dogen/staging/, which is working space. Add it to $REPO/.gitignore?" 1 \
            "yes|append the line" \
            "no|leave .gitignore alone (dogen's checks will warn)"
        [ "$answer" = "yes" ] || GITIGNORE=0
    fi
fi

compat_base="$HOME"
[ "$SKILLS" = "project" ] && compat_base="$REPO"

# --- install -----------------------------------------------------------------
if [ "$VERIFY_ONLY" -eq 0 ]; then
    explain ""
    say "Installing"
    mkdir -p "$TOOL_DIR" || die "cannot create $TOOL_DIR"
    [ -w "$TOOL_DIR" ] || die "$TOOL_DIR is not writable; pick another --tool-dir, or run the copy yourself with the access you have"
    rm -f "$TOOL_DIR/dogen"
    if [ "$LINK" -eq 1 ]; then
        ln -s "$DOGEN_SRC/dogen.py" "$TOOL_DIR/dogen" || die "cannot link into $TOOL_DIR"
        say "  linked  $TOOL_DIR/dogen -> $DOGEN_SRC/dogen.py"
    else
        cp "$DOGEN_SRC/dogen.py" "$TOOL_DIR/dogen" || die "cannot copy into $TOOL_DIR"
        chmod +x "$TOOL_DIR/dogen"
        say "  copied  $DOGEN_SRC/dogen.py -> $TOOL_DIR/dogen"
    fi

    mkdir -p "$SKILLS_ROOT" || die "cannot create $SKILLS_ROOT"
    for skill in $SKILL_NAMES; do
        rm -rf "${SKILLS_ROOT:?}/$skill"
        cp -r "$DOGEN_SRC/skills/$skill" "$SKILLS_ROOT/$skill" || die "cannot copy $skill"
    done
    say "  copied  $SKILL_NAMES -> $SKILLS_ROOT/"

    # Some agents read only .claude/skills/. A relative symlink per skill keeps
    # one copy on disk and every discovery root pointing at it. The relative
    # path is computed between PHYSICAL directories: a relative link resolves
    # from where the link really lives, and `.claude` is often itself a symlink
    # into a dotfiles checkout.
    if [ "$COMPAT_LINKS" -eq 1 ]; then
        compat_dir="$compat_base/.claude/skills"
        mkdir -p "$compat_dir" || die "cannot create $compat_dir"
        for skill in $SKILL_NAMES; do
            rel="$(python3 -c 'import os,sys; print(os.path.relpath(os.path.realpath(sys.argv[1]), os.path.realpath(sys.argv[2])))' "$SKILLS_ROOT/$skill" "$compat_dir")"
            rm -rf "${compat_dir:?}/$skill"
            ln -s "$rel" "$compat_dir/$skill" || die "cannot link $compat_dir/$skill"
        done
        say "  linked  $SKILL_NAMES from $compat_dir/"
    fi

    if [ "$SKILLS" = "project" ] && [ "$GITIGNORE" -eq 1 ]; then
        if ! grep -qxF '.dogen/staging/' "$REPO/.gitignore" 2>/dev/null; then
            printf '.dogen/staging/\n' >>"$REPO/.gitignore"
            say "  added   .dogen/staging/ to $REPO/.gitignore"
        fi
    fi
fi

# --- verify ------------------------------------------------------------------
checks=0
failures=0
warnings=0

pass() { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
fail() { checks=$((checks + 1)); failures=$((failures + 1)); printf '  FAIL  %s\n' "$1"; }
warn() { checks=$((checks + 1)); warnings=$((warnings + 1)); printf '  warn  %s\n' "$1"; }

say ""
say "Verifying"

# python
if python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
    pass "python3 is $(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])') (3.9 or newer)"
else
    fail "python3 3.9 or newer is required and was not found on PATH"
fi

# the tool on PATH
on_path=0
case ":$PATH:" in
    *":$TOOL_DIR:"*) on_path=1 ;;
esac
if [ -x "$TOOL_DIR/dogen" ]; then
    pass "dogen is at $TOOL_DIR/dogen"
else
    fail "no executable dogen at $TOOL_DIR/dogen"
fi
if [ "$on_path" -eq 1 ]; then
    resolved="$(PATH="$PATH" command -v dogen 2>/dev/null)" || resolved=""
    if [ "$resolved" = "$TOOL_DIR/dogen" ]; then
        pass "'dogen' on PATH resolves to that file"
    else
        fail "'dogen' on PATH resolves to '${resolved:-nothing}', not $TOOL_DIR/dogen — an older copy sits earlier on PATH"
    fi
else
    warn "$TOOL_DIR is not on PATH; add this line to your shell profile:  export PATH=\"$TOOL_DIR:\$PATH\""
fi

# version and contract, compared as literal strings with the skills' frontmatter
version_json="$("$TOOL_DIR/dogen" version --json 2>/dev/null)" || version_json=""
tool_version="$(printf '%s' "$version_json" | python3 -c 'import json,sys
try:
    d = json.load(sys.stdin); print(d["tool"]); print(d["contract"])
except Exception:
    pass' 2>/dev/null)"
tool_ver="$(printf '%s\n' "$tool_version" | sed -n 1p)"
tool_contract="$(printf '%s\n' "$tool_version" | sed -n 2p)"
if [ -n "$tool_ver" ] && [ -n "$tool_contract" ]; then
    pass "the dogen tool runs: version $tool_ver, contract $tool_contract"
else
    fail "the dogen tool did not run (is python3 on PATH?)"
fi

# the skills
for skill in $SKILL_NAMES; do
    dir="$SKILLS_ROOT/$skill"
    if [ -f "$dir/SKILL.md" ] && [ -f "$dir/references/routing.md" ]; then
        pass "$skill is installed at $dir"
    else
        fail "$skill is missing or incomplete at $dir"
        continue
    fi
    want_contract="$(sed -n 's/^  dogen_contract: *//p' "$dir/SKILL.md" | head -1)"
    want_tool="$(sed -n 's/^  dogen_min_tool: *"\{0,1\}\([^"]*\)"\{0,1\}$/\1/p' "$dir/SKILL.md" | head -1)"
    if [ -n "$tool_contract" ] && [ "$want_contract" != "$tool_contract" ]; then
        fail "$skill was written against contract $want_contract; the tool answers $tool_contract"
    fi
    if [ -n "$tool_ver" ] && [ -n "$want_tool" ] && [ "$want_tool" != "$tool_ver" ]; then
        # A newer tool is fine; the skill checks "older than min_tool" as a
        # literal comparison. Report the pair rather than parse versions.
        warn "$skill names min_tool $want_tool; the tool is $tool_ver — the skill stops only if the tool is older"
    fi
done

# the .claude/skills/ links, for the agents that read only that root
if [ "$COMPAT_LINKS" -eq 1 ]; then
    for skill in $SKILL_NAMES; do
        link="$compat_base/.claude/skills/$skill"
        if [ -L "$link" ] && [ -f "$link/SKILL.md" ] \
            && [ "$(cd "$link" && pwd -P)" = "$(cd "$SKILLS_ROOT/$skill" && pwd -P)" ]; then
            pass "$link links to the installed $skill"
        else
            fail "$link is not a link to $SKILLS_ROOT/$skill (agents that read only .claude/skills/ will miss it)"
        fi
    done
fi

# stale discovery roots: a real copy (not the installer's link) an agent may pick up first
stale_base="$compat_base"
for root in .claude/skills .github/skills .opencode/skills; do
    for skill in $SKILL_NAMES; do
        candidate="$stale_base/$root/$skill"
        [ -e "$candidate" ] || continue
        [ "$stale_base/$root" = "$SKILLS_ROOT" ] && continue
        if [ -L "$candidate" ] && [ "$(cd "$candidate" 2>/dev/null && pwd -P)" = "$(cd "$SKILLS_ROOT/$skill" && pwd -P)" ]; then
            continue
        fi
        warn "a stale copy of $skill sits at $stale_base/$root/ and may be discovered first; remove it"
    done
done

# the repository
if [ "$SKILLS" = "project" ]; then
    if [ -n "$(git -C "$REPO" config user.name)" ] && [ -n "$(git -C "$REPO" config user.email)" ]; then
        pass "git identity is set in $REPO"
    else
        warn "no git identity in $REPO; dogen commits and needs one:  git config user.name \"You\" && git config user.email you@example.com"
    fi
    if grep -qxF '.dogen/staging/' "$REPO/.gitignore" 2>/dev/null; then
        pass ".dogen/staging/ is ignored"
    else
        warn ".dogen/staging/ is not in $REPO/.gitignore; dogen's checks will warn until it is"
    fi
fi

# --- uninstall ---------------------------------------------------------------
# The commands that remove what this run placed, with the paths it used. Printed
# only after an install, never under --verify-only, and never run here.
print_uninstall() {
    [ "$VERIFY_ONLY" -eq 0 ] || return 0
    local skill
    say ""
    say "To uninstall, run:"
    printf '  rm -f %q\n' "$TOOL_DIR/dogen"
    for skill in $SKILL_NAMES; do
        printf '  rm -rf %q\n' "$SKILLS_ROOT/$skill"
    done
    if [ "$COMPAT_LINKS" -eq 1 ]; then
        for skill in $SKILL_NAMES; do
            printf '  rm -f %q\n' "$compat_base/.claude/skills/$skill"
        done
    fi
    if [ "$SKILLS" = "project" ] && grep -qxF '.dogen/staging/' "$REPO/.gitignore" 2>/dev/null; then
        say "Then delete the line .dogen/staging/ from $REPO/.gitignore."
    fi
    if [ "$LINK" -eq 1 ]; then
        say "The checkout at $DOGEN_SRC is yours to keep or delete."
    fi
    say "Uninstalling leaves your pages and the record under .dogen/ in place."
}

# --- report ------------------------------------------------------------------
say ""
if [ "$checks" -eq 0 ]; then
    say "install: nothing was checked"
    exit 2
fi
if [ "$failures" -ne 0 ]; then
    say "install: $failures check(s) failed, $warnings warning(s)"
    print_uninstall
    exit 1
fi
say "install: every check passed, $warnings warning(s)"
say ""
say "Next: open your agent in ${REPO:-your docs repository}. Run /dogen-onboard once,"
say "then /dogen-plan, /dogen-write and /dogen-review."
print_uninstall
exit 0
