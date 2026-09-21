#!/usr/bin/env bash
# install.sh — install dogen and its three skills, then verify the install.
#
# Usage:
#   ./install.sh                 walk through every decision; Enter takes the default
#   ./install.sh --yes           take every default without asking
#   ./install.sh --verify-only   check an existing install and report
#   ./install.sh --help          every flag
#
# Decisions, in order (each one is also a flag, so a script can answer it):
#   1. which agent you drive     --agent claude-code|copilot|codex|cursor|other
#   2. where the skills go       --skills project|global   [--repo DIR] [--skills-root DIR]
#   3. where the tool goes       --tool-dir DIR | --link
#   4. .gitignore                --no-gitignore
# Then the install is verified. Exit 0 when every check passed, 1 when one
# failed, 2 when nothing could be checked. The script never runs git init, git
# commit, sudo, or anything else that changes a repository's history.

set -u

# --- defaults ----------------------------------------------------------------
DOGEN_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT=""
SKILLS=""
REPO=""
SKILLS_ROOT=""
TOOL_DIR=""
LINK=0
GITIGNORE=1
YES=0
VERIFY_ONLY=0
answer=""

DEFAULT_TOOL_DIR="$HOME/.local/bin"
GLOBAL_SKILLS_ROOT="$HOME/.agents/skills"
SKILL_NAMES="dogen-plan dogen-write dogen-review"

usage() {
    sed -n '2,17p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    cat <<'EOF'

Flags:
  --yes                 answer every prompt with its default
  --agent NAME          claude-code (default), copilot, codex, cursor or other
  --skills SCOPE        project (default) or global
  --repo DIR            the docs repository (project scope; default: the current directory)
  --skills-root DIR     where the skills go, when the default discovery root is not right
  --tool-dir DIR        where the dogen executable is copied (default: ~/.local/bin)
  --link                symlink the executable into the checkout instead of copying it
  --no-gitignore        do not add .dogen/staging/ to the repository's .gitignore
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
        --agent) shift; AGENT="${1:-}" ;;
        --skills) shift; SKILLS="${1:-}" ;;
        --repo) shift; REPO="${1:-}" ;;
        --skills-root) shift; SKILLS_ROOT="${1:-}" ;;
        --tool-dir) shift; TOOL_DIR="${1:-}" ;;
        --link) LINK=1 ;;
        --no-gitignore) GITIGNORE=0 ;;
        --dogen-src) shift; DOGEN_SRC="${1:-}" ;;
        --verify-only) VERIFY_ONLY=1 ;;
        -h|--help) usage; exit 0 ;;
        *) die "unknown flag $1 (try --help)" ;;
    esac
    shift
done

[ -f "$DOGEN_SRC/dogen" ] || die "no dogen executable at $DOGEN_SRC (pass --dogen-src)"
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

# Prompt text is shown only when a prompt will follow it.
explain() {
    if [ "$YES" -eq 0 ] && [ -t 0 ]; then
        printf '%s\n' "$*"
    fi
}

# --- decision 1: the agent ---------------------------------------------------
if [ -z "$AGENT" ]; then
    default_agent="claude-code"
    if [ -n "${COPILOT_CLI:-}" ] || [ -n "${GITHUB_COPILOT_CLI:-}" ]; then
        default_agent="copilot"
    elif [ -n "${CODEX_HOME:-}" ]; then
        default_agent="codex"
    fi
    explain ""
    explain "1/4  Which agent will drive the skills?"
    explain "     claude-code · copilot · codex · cursor · other"
    explain "     Every one of these reads the .agents/skills/ discovery root; the answer"
    explain "     only changes the hint printed at the end (and 'other' asks for a root)."
    ask AGENT "     agent" "$default_agent"
fi
case "$AGENT" in
    claude-code|copilot|codex|cursor|other) ;;
    *) die "--agent must be claude-code, copilot, codex, cursor or other (got '$AGENT')" ;;
esac

# --- decision 2: skills scope ------------------------------------------------
if [ -z "$SKILLS" ]; then
    explain ""
    explain "2/4  Where should the skills be installed?"
    explain "     project — into the docs repository's .agents/skills/, so they travel with it"
    explain "     global  — once, into ~/.agents/skills/, so every repository discovers them"
    ask SKILLS "     scope" "project"
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
        if [ "$AGENT" = "other" ]; then
            ask SKILLS_ROOT "     skills root inside the repository" ".agents/skills"
        else
            SKILLS_ROOT=".agents/skills"
        fi
    fi
    case "$SKILLS_ROOT" in
        /*) ;;
        *) SKILLS_ROOT="$REPO/$SKILLS_ROOT" ;;
    esac
else
    if [ -z "$SKILLS_ROOT" ]; then
        if [ "$AGENT" = "other" ]; then
            ask SKILLS_ROOT "     global skills root" "$GLOBAL_SKILLS_ROOT"
        else
            SKILLS_ROOT="$GLOBAL_SKILLS_ROOT"
        fi
    fi
fi

# --- decision 3: the tool ----------------------------------------------------
if [ "$LINK" -eq 0 ] && [ -z "$TOOL_DIR" ]; then
    explain ""
    explain "3/4  Where should the dogen executable go?"
    explain "     $DEFAULT_TOOL_DIR   copy, no sudo, the usual place for user tools (default)"
    explain "     /usr/local/bin      copy, for every user; needs write access to that directory"
    explain "     link                a symlink into this checkout: git pull upgrades the tool"
    explain "     any other path      a directory of your own"
    ask TOOL_DIR "     directory" "$DEFAULT_TOOL_DIR"
    if [ "$TOOL_DIR" = "link" ]; then
        LINK=1
        TOOL_DIR=""
    fi
fi
if [ "$LINK" -eq 1 ] && [ -z "$TOOL_DIR" ]; then
    TOOL_DIR="$DEFAULT_TOOL_DIR"
fi
case "$TOOL_DIR" in
    "~"*) TOOL_DIR="$HOME${TOOL_DIR#"~"}" ;;
esac

# --- decision 4: .gitignore --------------------------------------------------
if [ "$SKILLS" = "project" ] && [ "$GITIGNORE" -eq 1 ] && [ "$VERIFY_ONLY" -eq 0 ]; then
    if ! grep -qxF '.dogen/staging/' "$REPO/.gitignore" 2>/dev/null; then
        explain ""
        explain "4/4  dogen stages drafts under .dogen/staging/, which is working space."
        ask answer "     add .dogen/staging/ to $REPO/.gitignore? (y/n)" "y"
        case "$answer" in
            y|Y|yes) ;;
            *) GITIGNORE=0 ;;
        esac
    fi
fi

# --- install -----------------------------------------------------------------
if [ "$VERIFY_ONLY" -eq 0 ]; then
    explain ""
    say "Installing"
    mkdir -p "$TOOL_DIR" || die "cannot create $TOOL_DIR"
    [ -w "$TOOL_DIR" ] || die "$TOOL_DIR is not writable; pick another --tool-dir, or run the copy yourself with the access you have"
    rm -f "$TOOL_DIR/dogen"
    if [ "$LINK" -eq 1 ]; then
        ln -s "$DOGEN_SRC/dogen" "$TOOL_DIR/dogen" || die "cannot link into $TOOL_DIR"
        say "  linked  $TOOL_DIR/dogen -> $DOGEN_SRC/dogen"
    else
        cp "$DOGEN_SRC/dogen" "$TOOL_DIR/dogen" || die "cannot copy into $TOOL_DIR"
        chmod +x "$TOOL_DIR/dogen"
        say "  copied  $DOGEN_SRC/dogen -> $TOOL_DIR/dogen"
    fi

    mkdir -p "$SKILLS_ROOT" || die "cannot create $SKILLS_ROOT"
    for skill in $SKILL_NAMES; do
        rm -rf "${SKILLS_ROOT:?}/$skill"
        cp -r "$DOGEN_SRC/skills/$skill" "$SKILLS_ROOT/$skill" || die "cannot copy $skill"
    done
    say "  copied  $SKILL_NAMES -> $SKILLS_ROOT/"

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
    pass "dogen version --json answers tool $tool_ver, contract $tool_contract"
else
    fail "dogen version --json did not answer (is python3 on PATH for the tool?)"
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

# stale discovery roots, which an agent may pick up before the right one
stale_base="$HOME"
[ "$SKILLS" = "project" ] && stale_base="$REPO"
for root in .claude/skills .github/skills .opencode/skills; do
    for skill in $SKILL_NAMES; do
        if [ -e "$stale_base/$root/$skill" ] && [ "$stale_base/$root" != "$SKILLS_ROOT" ]; then
            warn "a stale copy of $skill sits at $stale_base/$root/ and may be discovered first; remove it"
        fi
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
        warn ".dogen/staging/ is not in $REPO/.gitignore; dogen verify will warn (V17) until it is"
    fi
fi

# --- report ------------------------------------------------------------------
say ""
if [ "$checks" -eq 0 ]; then
    say "install: nothing was checked"
    exit 2
fi
if [ "$failures" -ne 0 ]; then
    say "install: $failures check(s) failed, $warnings warning(s)"
    exit 1
fi
say "install: every check passed, $warnings warning(s)"
say ""
say "Next: open your agent in ${REPO:-your docs repository} and start a unit."
case "$AGENT" in
    claude-code) say "  /dogen-plan" ;;
    copilot|codex|cursor|other) say "  \"Use the dogen-plan skill to document …\"" ;;
esac
say "Then dogen-write drafts it and dogen-review records your verdict."
exit 0
