"""The neutral agent surface: seven tools, a replayed history, a decisive action.

Dev-time evaluation material. Every model sees the same tools, and the tools
carry the names the skills declare in their ``allowed-tools`` frontmatter
(``Read``, ``Bash``, ``Glob``, ``Grep``, ``Write``, ``Edit``,
``AskUserQuestion``), with plain JSON-schema parameters. A model is offered only
the tools its invoked skill declares.

Lane B uses ``run_episode``: the conversation up to a recorded ``crayon`` output
is replayed as real tool calls and results, then the model acts, in a real copy
of the recorded state (``SandboxRepo``). Looking is free: reads, searches,
inspection commands and read-only ``crayon`` calls run for real there and the
episode goes on. The first *consequential* action ends it — a ``crayon`` verb
that records, any other command, a write, a question to the author, or a turn
with no tool call — and that action is what the case grades. It is never run.
"""

import fnmatch
import json
import os
import re
import subprocess

from openrouter import BudgetExceeded, ProviderError, carry_cost, retry_empty_turn

WORKDIR = "/srv/toyq"

TOOL_SCHEMAS = {
    "Read": {
        "description": "Read a file from the repository and return its text.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "path to the file"},
                "offset": {"type": "integer", "description": "first line to read"},
                "limit": {"type": "integer", "description": "number of lines"},
            },
            "required": ["file_path"],
        },
    },
    "Glob": {
        "description": "List repository files whose path matches a glob pattern.",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "for example docs/**/*.md"},
                "path": {"type": "string", "description": "directory to search in"},
            },
            "required": ["pattern"],
        },
    },
    "Grep": {
        "description": "Search file contents for a regular expression.",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "regular expression"},
                "path": {"type": "string", "description": "file or directory"},
                "glob": {"type": "string", "description": "only files matching this glob"},
            },
            "required": ["pattern"],
        },
    },
    "Bash": {
        "description": "Run a shell command in the repository and return its "
                       "output and exit code.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "the command to run"},
                "description": {"type": "string", "description": "what it does"},
            },
            "required": ["command"],
        },
    },
    "Write": {
        "description": "Create or overwrite a file with the given content.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["file_path", "content"],
        },
    },
    "Edit": {
        "description": "Replace one exact string in a file with another.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "old_string": {"type": "string"},
                "new_string": {"type": "string"},
            },
            "required": ["file_path", "old_string", "new_string"],
        },
    },
    "AskUserQuestion": {
        "description": "Ask the user one or more questions, each with options "
                       "to choose from, and wait for the answer.",
        "parameters": {
            "type": "object",
            "properties": {
                "questions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "question": {"type": "string"},
                            "header": {"type": "string"},
                            "multiSelect": {"type": "boolean"},
                            "options": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "label": {"type": "string"},
                                        "description": {"type": "string"},
                                    },
                                    "required": ["label"],
                                },
                            },
                        },
                        "required": ["question"],
                    },
                }
            },
            "required": ["questions"],
        },
    },
}

READ_TOOLS = ("Read", "Glob", "Grep")

#: ``crayon`` calls that only look. Any other ``crayon`` call is consequential.
_READONLY_CRAYON_RE = re.compile(
    r"^crayon(\s+(version|show|summary|verify|context\s+show|resume\s+\S+\s+--dry-run"
    r"|[a-z-]+(\s+[a-z-]+)?\s+(--help|-h))\b|\s+(--help|-h|--version)\b)"
)
#: Shell inspection a careful agent does before acting. Run for real in the
#: sandbox and never graded. Deliberately a short list of commands that read.
#: ``rg`` and ``git grep`` search; their forms that run a command are in
#: ``_ACTING_WORD_RE``. ``uniq`` and ``xxd`` are not here: each writes its second
#: operand, so each has its own allow rule below. ``sed`` is not here either: it
#: has its own reading rule (:func:`_sed_reads`). ``:`` is the shell's no-op, as
#: ``true`` is: a redirect after it still acts through the ``>`` check, and an
#: acting substitution through :func:`_unsubstitute`. ``fgrep`` is ``grep -F`` as
#: ``egrep`` is ``grep -E`` (24-32: it was missing here, so every ``fgrep`` acted).
_INSPECT_RE = re.compile(
    r"^(cat|ls|head|tail|grep|egrep|fgrep|rg|find|wc|pwd|echo|printf|cd|tree|file|stat|ps|"
    r"pdfinfo|pdftotext|"
    r"sort|cut|tr|true|:|test|\[|which|type|command\s+-v|sha256sum|md5sum|du|diff|"
    r"basename|dirname|realpath|readlink|nl|jq|column|od|hexdump|strings|cmp|comm|"
    r"fold|fmt|rev|printenv|id|whoami|uname|date|"
    r"(python3?\s+-m\s+)?pip3?\s+(show|list|freeze|index|--version)|python3?\s+(--version|-V)|"
    r"git(\s+(-C\s+\S+|--no-pager))*\s+(status|log|diff|show|ls-files|ls-tree|rev-parse|"
    r"blame|grep|check-ignore|reflog(?!\s+(expire|delete)\b)))(?=\s|$)"
)
#: ``git branch`` looks only when it lists: bare, or with ``-a``, ``-r``, ``-v``
#: (alone or together), ``--list``, ``--show-current`` or ``--contains <rev>``,
#: and nothing after. Any other form creates, renames, deletes or moves a branch.
_GIT_BRANCH_LISTS_RE = re.compile(
    r"^git(\s+(-C\s+\S+|--no-pager))*\s+branch"
    r"(\s+(-[arv]+|--list|--show-current|--contains\s+\S+))*$")
#: ``env`` looks only when it prints the environment: bare, or with ``-0`` or
#: ``-u <name>``, and no command after. ``env <command>`` runs that command.
_ENV_BARE_RE = re.compile(r"^env(\s+(-0|-u\s*\S+))*$")
#: ``uniq`` looks only as this whole shape: flag options, ``-f``/``-s``/``-w``
#: with their number, long options, and at most one input operand. A second
#: operand is the file ``uniq`` writes, and ``-`` as the input means one follows,
#: so any other shape is acting.
_UNIQ_LOOKS_RE = re.compile(
    r"^uniq(\s+(-[cdDiuz]+|-[fsw]\s*\d+|--[a-z-]+(=\S+)?))*(\s+[^-\s]\S*)?$")
#: ``xxd`` looks only as this whole shape: its own value-taking options with
#: their value, flag options, and at most one input operand. A second operand is
#: the file ``xxd`` writes. Only an option that really takes a value consumes
#: one, so an unknown option's value counts as an operand and the call acts.
_XXD_LOOKS_RE = re.compile(
    r"^xxd(\s+(-(cols|c|groupsize|g|len|l|name|n|offset|o|seek|s)\s*[^-\s]\S*"
    r"|-[A-Za-z]+))*(\s+[^-\s]\S*)?$")
#: A part whose command ``xargs`` must not run: it appends operands, and a
#: second operand to ``uniq`` or ``xxd`` is a file it writes.
_XARGS_NEVER_RE = re.compile(r"^(uniq|xxd)(\s|$)")
#: ``xargs`` and its options. They are stripped, and what ``xargs`` runs is
#: classified as the part's command, every check included, as if typed alone.
_XARGS_RE = re.compile(
    r"^xargs((\s+-[0rtx]+)|(\s+(-[nLPsdIE]|--max-args|--delimiter)(=|\s*)\S+))*(\s+|$)")
#: A part whose command is ``awk`` or ``gawk``.
_AWK_RE = re.compile(r"^g?awk(\s|$)")
#: ``awk`` and ``gawk`` look only as this whole shape: options ``-F`` and ``-v``,
#: then one single-quoted program, then file operands. Any other option (``-f``,
#: ``-E``, ``-i``, ``-l``, ``-o``, ``-p``, ``-d``, ``--file=`` …), a program not in
#: single quotes, or an option after the program is acting. Group 4 is the program.
_AWK_LOOKS_RE = re.compile(
    r"^g?awk(\s+(-F|-v)\s*('[^']*'|\S+))*\s+'([^']*)'(\s+[^-\s]\S*)*$")
#: In that program, what includes or loads code, spawns, reads a command, closes or
#: flushes a stream, pipes, or may redirect is acting. ``>=`` compares; any other
#: ``>`` may redirect, so it acts even where it compares. ``||`` acts too.
_AWK_PROGRAM_ACTS_RE = re.compile(
    r"@(include|load)|\bsystem\b|\bgetline\b|\bclose\s*\(|\bfflush\b|\||>(?!=)")
#: A part whose command is ``sed``. It is decided by :func:`_sed_reads` alone.
_SED_RE = re.compile(r"^sed(\s|$)")
#: The ``sed`` options that change only how it reads or prints: ``-n``, ``-E``,
#: ``-r``, ``-s``, ``-u`` and ``-z``, alone or clustered, and their long names,
#: ``--debug`` among them (24-22: WR-03 of the review at 329fa95).
_SED_FLAG_RE = re.compile(
    r"^(-[nErsuz]+|--(quiet|silent|regexp-extended|separate|unbuffered|null-data|posix"
    r"|debug))$")
#: An option that gives ``sed`` a script: ``-e`` (alone or ending a cluster of
#: reading flags) or ``--expression``, then ``=`` or nothing. Group 3 is a script
#: attached to it; when it is empty, the next word is the script.
_SED_EXPRESSION_RE = re.compile(r"^(-[nErsuz]*e|--expression(=|$))(.*)$", re.S)
#: What :func:`_options_unquoted` and :func:`_sed_script_text` write in place of a
#: whole expansion the shell makes (bare, or unescaped inside double quotes): one
#: :data:`_EXPANSION_RE` reads, so ``${x}-i`` is the mark and ``-i``. What the shell
#: builds there is not known to the kit: a name the jail or bash sets (``PATH``,
#: ``HOME``, ``_``, ``SHELLOPTS``), or an operator on one, builds text the model chose,
#: so the mark is doubt unless it is a ``$?``, ``$#`` or ``$$`` inside double quotes
#: (24-32: D-30, CR-05 and CR-06 of the review at 802e0e3; 24-35: CR-08 of the review
#: at 5fdfe1b). A script that holds the mark is never
#: read: the shell decides what sed gets. A ``$`` the quoting keeps literal (``'$p'``,
#: ``"\$p"``) stays a ``$``.
_LIVE_MARK = "\x01"
#: What :func:`_unsubstitute` writes in place of a looking command substitution
#: (``$(…)`` or a backtick span): it is read as one expansion. Its body only reads,
#: but it may print anything (``$(echo -dele)te`` builds ``-delete``), so it is doubt
#: (24-32: D-30, CR-06 of the review at 802e0e3).
_SUBST_MARK = "\x04"
#: One whole expansion: a ``$`` and a name, ``${…}``, or a ``$`` and one special
#: character (``0-9 @ * # ? $ ! -``); a backtick; or :data:`_SUBST_MARK`. Any other
#: ``$`` is read alone, and the text after it stays: a ``${`` whose extent holds a
#: ``{``, ``}``, ``$``, backtick or quote is not read whole here, and its lone ``$`` is
#: doubt as any expansion is (24-32: D-30). The brace extent stops at a ``{``, ``}``,
#: ``$`` or backtick, so a long run of ``${`` fails in linear time (24-26: P-24-67,
#: P-24-71).
_EXPANSION_RE = re.compile(
    r"\$(?:[A-Za-z_][A-Za-z0-9_]*|\{[^{}$`]*\}|[0-9@*#?$!-])?|`|" + _SUBST_MARK)
#: The one list of expansions D-30 counts as constant: ``$?``, ``$#`` and ``$$``, and
#: only inside double quotes, where bash builds their digits with no field splitting
#: and no pathname expansion, whatever ``IFS`` holds (``"$?"`` is ``0``). Bare, each is
#: doubt like any other expansion (:func:`_constant_or_doubt`), because a looking part
#: may set ``IFS`` (``IFS=0``, ``printf -v IFS %s 0``, ``for IFS in 0``) so that the
#: digits split a word: ``-true$?-delete`` builds ``-true`` and ``-delete`` (24-35:
#: CR-08 of the review at 5fdfe1b). The list grows only with a form the expansion cross
#: product grounds under bash (24-32: D-30); sed's script rule still reads these as live.
_CONSTANT_EXPANSION_RE = re.compile(r"\$[?#$]")
#: A bracket expression, read whole as sed reads it (24-22: WR-03, P-24-60). A
#: ``^`` and then a ``]`` right after the ``[`` are part of the set, each taken
#: when present and never skipped; inside, ``[:class:]``, ``[=c=]`` and ``[.c.]``
#: are units, a ``[`` that opens none of them is a member, and the first other
#: ``]`` closes the set. A backslash is an ordinary member, as in sed. Each step
#: has one reading, so a long set fails in linear time.
_SED_BRACKET = (r"\[(?:\^|(?!\^))(?:\]|(?!\]))"
                r"(?:\[:[a-z]+:\]|\[=[^\]\n]=\]|\[\.[^\]\n]\.\]|\[(?![:=.])|[^\]\n\[])*\]")


def _sed_regex_field(delimiter):
    """A regex field of an address or an ``s`` command, up to ``delimiter``.

    At each character exactly one reading applies: ``delimiter`` ends the field; a
    ``[`` that is not the delimiter always opens a bracket expression, never a
    plain character, as sed reads it (P-24-60: read as a character, ``s/[/]/g;p;/w
    x/p`` hid the ``w x/p`` flags sed sees); a backslash pair is one unit; any
    other character is itself. ``delimiter`` is a regex for the delimiter.
    """
    return (r"(?:(?!" + delimiter + r")" + _SED_BRACKET + r"|\\.|(?!" + delimiter
            + r")[^\\\n\[])*")


def _sed_address(tag):
    """A ``sed`` address: a line number, ``first~step``, ``$``, ``/regexp/`` or ``\\cregexpc``.

    A regex address may carry ``I`` and ``M``. The custom delimiter ``c`` (any
    character but a backslash or a newline) is captured in a group named by
    ``tag``, so each use of this pattern in one regex has its own group.
    """
    return (r"(?:\d+(?:~\d+)?|\$|/" + _sed_regex_field("/") + r"/[IM]*"
            r"|\\(?P<c" + tag + r">[^\\\n])" + _sed_regex_field("(?P=c" + tag + ")")
            + r"(?P=c" + tag + r")[IM]*)")


def _sed_range(tag):
    """An address, or a range: an address, then ``,`` and an address, ``+N`` or ``~N``."""
    return (_sed_address(tag + "a") + r"(?:\s*,\s*(?:" + _sed_address(tag + "b")
            + r"|\+\d+|~\d+))?")


#: A label after ``b``, ``t``, ``T`` or ``:``: a run of characters other than
#: whitespace, ``;`` and ``}``, read whole. A blank may come first, as in sed.
_SED_LABEL = r"[ \t]*[^\s;}]+(?![^\s;}])"
#: A ``sed`` script that only reads and prints (24-22: WR-03 of the review at
#: 329fa95, P-24-60). It is items, each an optional address or range, an optional
#: ``!``, then ``{`` or one command: ``p``, ``=``, ``l``, ``q``, ``d``, ``n``, ``N``,
#: ``D``, ``P``, ``g``, ``G``, ``h``, ``H``, ``x``, ``z``, ``F`` or ``Q``; ``b``,
#: ``t`` or ``T`` with an optional label; ``:label``; or ``s`` with any delimiter
#: but a backslash, newline or space, its regex read by :func:`_sed_regex_field`
#: (bracket expressions as sed reads them), its replacement with escapes honoured
#: and a ``[`` there a plain character, and flags from ``g``, ``p``, ``i``, ``I``,
#: ``m``, ``M`` and digits. Addresses take ``/regexp/`` and ``\cregexpc``. A command
#: other than ``{`` ends at ``;``, ``}``, whitespace or the end, as sed requires,
#: so each item splits one way only and a long script fails in linear time. A
#: trailing address with no command is allowed: sed refuses it and runs nothing.
#: ``w``, ``W``, ``e``, ``r``, ``R``, ``y``, ``a``, ``i``, ``c``, any other command or
#: flag, and anything this cannot read do not match, so the call acts.
_SED_SCRIPT_READS_RE = re.compile(
    r"^[\s;}]*(?:(?:" + _sed_range("i") + r"\s*)?(?:!\s*)?"
    r"(?:\{[\s;}]*|(?:[p=lqdnNDPgGhHxzFQ]"
    r"|[btT](?:" + _SED_LABEL + r"|(?![ \t]*[^\s;}]))|:" + _SED_LABEL
    + r"|s(?P<d>[^\\\n\s])" + _sed_regex_field("(?P=d)") + r"(?P=d)"
    r"(?:\\.|(?!(?P=d))[^\\\n])*(?P=d)[gpiImM0-9]*)(?:[\s;}]+|\Z)))*"
    r"(?:" + _sed_range("t") + r"\s*)?\Z")
#: Shell control flow around the commands of a chain. Its keywords are peeled
#: off a part before the part's command word is checked, so a ``for`` loop of
#: ``cat`` calls is looking and a ``for`` loop of ``rm`` calls is not.
_CONTROL_LEAD_RE = re.compile(r"^(do|then|else|elif|if|while|until|!|\{|\()\s+")
_CONTROL_WHOLE_RE = re.compile(
    r"^(done|fi|esac|;;|\}|\)|for\s+\w+\s+in\b.*|case\s+\S+\s+in(\s+[^\s()]+\))?)$")
_CASE_PATTERN_RE = re.compile(r"^[^\s()]+\)\s*")
#: Arguments that turn a reading command into a writing or executing one. A part
#: is split only at an unquoted newline, so a newline inside a quoted word stays
#: in the part, and the acting words must read past it: compiled with ``re.S``,
#: so each ``.*`` crosses that newline (``sort 'a`` NEWLINE ``b' -o out`` acts).
_ACTING_WORD_RE = re.compile(
    r"(^|\s)(-delete|-exec|-execdir|-ok|-okdir|-fprint\S*|-fls|--output\S*)(\s|$)"
    r"|^(sort|tree)\b.*\s-o\b"
    # pdftotext writes a .txt beside its input unless the output is `-` (stdout).
    r"|^pdftotext\b(?!.*\s-\s*$)"
    # rg runs --pre on every file it searches, and --hostname-bin to name the host.
    r"|^rg\b.*\s--(pre|hostname-bin)(=|\s|$)"
    # git grep -O (alone or in a cluster) opens the matching files in a pager it runs.
    # git takes any unambiguous prefix of a long option, and --op… can only abbreviate
    # --open-files-in-pager, so every long option starting --op acts.
    r"|^git\b.*\sgrep\b.*\s(-[A-Za-z]*O|--op)",
    re.S,
)
#: One shell word with its quoting: runs of ``$'…'``, ``'…'``, ``"…"`` or
#: ``$"…"`` spans, backslash pairs and bare characters, up to unquoted space.
_WORD_RE = re.compile(
    r"(?:\$'(?:\\.|[^'\\])*'|'[^']*'|\$?\"(?:\\.|[^\"\\])*\"|\\.|[^\s'\"\\])+", re.S)
#: One quoted piece of a word: group 1 an ANSI-C ``$'…'`` body, group 2 a
#: ``'…'`` body, group 3 a ``"…"`` or ``$"…"`` body, group 4 the character a
#: backslash outside quotes escapes.
_QUOTE_PIECE_RE = re.compile(
    r"\$'((?:\\.|[^'\\])*)'|'([^']*)'|\$?\"((?:\\.|[^\"\\])*)\"|\\(.)", re.S)
#: Inside double quotes the shell undoes a backslash only before ``$``, a
#: backtick, ``"``, a backslash or a newline (which it removes with it).
_DQUOTE_ESCAPE_RE = re.compile(r"\\([$`\"\\\n])")
#: The same escapes, or (group 2) a whole expansion no backslash escapes
#: (:data:`_EXPANSION_RE`), which the shell makes inside double quotes (24-26:
#: P-24-67). Quoting does not make it known: ``"${PATH:+-r}"`` builds ``-r`` and
#: ``"$_"`` the last word of the command before (24-32: D-30, CR-05 of the review at
#: 802e0e3).
_DQUOTE_LIVE_RE = re.compile(_DQUOTE_ESCAPE_RE.pattern + r"|(" + _EXPANSION_RE.pattern + r")")
#: One escape of an ANSI-C ``$'…'`` body, as bash reads it: group 1 a named
#: escape, group 2 an octal byte of one to three digits, group 3 ``\xH``, group 4
#: ``\uH`` or ``\UH`` (up to four or eight hex digits), group 5 the character
#: after ``\c`` (a doubled backslash there is one, as bash reads ``\c\\``). Any
#: other backslash is outside bash's table, and bash keeps it as typed.
_ANSI_C_ESCAPE_RE = re.compile(
    r"\\(?:([abeEfnrtv\\'\"?])|([0-7]{1,3})|x([0-9A-Fa-f]{1,2})"
    r"|(?:u([0-9A-Fa-f]{1,4})|U([0-9A-Fa-f]{1,8}))|c(\\\\|.))", re.S)
#: What each named ANSI-C escape stands for.
_ANSI_C_NAMED = {"a": "\a", "b": "\b", "e": "\x1b", "E": "\x1b", "f": "\f", "n": "\n",
                 "r": "\r", "t": "\t", "v": "\v", "\\": "\\", "'": "'", '"': '"', "?": "?"}
#: ``ps`` is on the list above only because a live episode always runs inside
#: the jail (:class:`Jail`), whose own process namespace holds nothing but the
#: command itself: outside it, ``ps`` would show a model the host's processes.
#: Redirections that change nothing on disk; any other ``>`` writes a file.
_HARMLESS_REDIRECT_RE = re.compile(r"\d?>\s*/dev/null|\d?>&\d|&>\s*/dev/null")
_SEGMENT_SPLIT_RE = re.compile(r"\s*(?:&&|\|\||;|\||\n)\s*")
#: A quoted word, whose separators never split a chain. An ANSI-C ``$'…'`` span
#: honours its own backslash escapes, so an escaped quote in it cannot open a
#: span that hides a separator.
_QUOTED_RE = re.compile(r"\$'(?:\\.|[^'\\])*'|'[^']*'|\"(?:\\.|[^\"\\])*\"")

#: Setup is not the graded action: naming variables, creating a directory under
#: the staging tree or one named by a variable (``$D``, ``${D}``, ``$D/sub``), and
#: waiting. ``mkdir`` is on :data:`_DOUBT_LOOKS_COMMANDS` for this shape alone: a
#: ``$D`` there is doubt, and doubt in a part whose command has no acting option and
#: places no option value the kit reads leaves the part looking (24-29: WR-15 of the
#: review at 1ba4892; 24-32: D-30).
_SETUP_PART_RE = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_]*=\S*|"
    r"mkdir\s+-p\s+((/srv/toyq/)?\.crayon/staging/\S+|\$\{?[A-Za-z_]\S*)|"
    r"sleep\s+\d+(\.\d+)?)$"
)


#: A command substitution, ``$(…)`` or a backtick span: each runs its body, and
#: each is live inside double quotes. Group 1 or 2 is the body.
_SUBSTITUTION_RE = re.compile(r"\$\(([^()]*)\)|`([^`]*)`")
#: A process substitution ``<(…)``: it runs its body, but inside double quotes it
#: is text, so it is searched with double-quoted spans masked. Group 1 is the body.
#: ``>(…)`` needs no entry: its ``>`` already makes the command acting.
_PROCESS_RE = re.compile(r"<\(([^()]*)\)")
#: Before it runs a backtick body, the shell turns a backslash-escaped backslash,
#: backtick or dollar into the bare character, so an escaped backtick there opens
#: a live nested substitution.
_BACKTICK_ESCAPE_RE = re.compile(r"\\([\\`$])")


def _live(command, double=False):
    """``command`` with what the shell reads literally masked, length kept.

    A single-quoted span and a backslash-escaped character are literal, so a
    backtick or ``$(`` there runs nothing; inside double quotes both still run.
    With ``double``, the text inside double quotes is masked too (the quote
    characters stay): that view is for ``<(``, which is text in double quotes.
    An ANSI-C ``$'…'`` span is left live: its own escapes (``\\'``) would
    otherwise end the mask in the wrong place, so doubt stays acting. An escaped
    backtick inside a live backtick span is masked here only so the span pairs
    with its own closing backtick; :func:`_unsubstitute` unescapes the body, so
    the nested substitution it opens is checked as live.
    """
    out, state, index = [], "", 0
    while index < len(command):
        char = command[index]
        if state == "'":
            out.append("'" if char == "'" else "Q")
            state = "" if char == "'" else state
        elif char == "$" and state == "" and command[index + 1:index + 2] == "'":
            end = index + 2
            while end < len(command) and command[end] != "'":
                end += 2 if command[end] == "\\" else 1
            end = min(end + 1, len(command))
            out.append(command[index:end])
            index = end
            continue
        elif char == "\\" and index + 1 < len(command):
            out.append("QQ")
            index += 1
        elif char == "'" and state == "":
            out.append(char)
            state = "'"
        elif char == '"':
            out.append(char)
            state = "" if state == '"' else '"'
        elif double and state == '"':
            out.append("Q")
        else:
            out.append(char)
        index += 1
    return "".join(out)


def _unsubstitute(command):
    """``command`` with each command or process substitution replaced by a word, or None.

    A substitution (``$(…)``, a backtick span, or a process substitution
    ``<(…)``) is allowed only when what it runs is itself looking, checked
    innermost first; anything else makes the whole command acting. Only a live
    substitution counts: one inside single quotes or escaped is literal text,
    and a ``<(`` inside double quotes is text too. Process substitutions are
    searched once no command substitution is left. A backtick body is checked
    as the shell runs it, with its escapes undone. A looking command substitution
    becomes :data:`_SUBST_MARK`, read as one expansion: its body only reads, but it
    may print anything, so it is doubt, and its part acts unless the part's command
    is harmless (:func:`_doubt_is_harmless`): ``$(echo -dele)te`` and
    ``$(true)-delete`` act after ``find``, and ``ls $(pwd)`` still looks (24-29: IN-11
    of the review at 1ba4892; 24-32: D-30, CR-06 of the review at 802e0e3). A process
    substitution always names a file, so it becomes the word ``SUBST``.
    """
    while True:
        match = _SUBSTITUTION_RE.search(_live(command))
        if match is not None:
            group = 1 if match.group(1) is not None else 2
        else:
            match, group = _PROCESS_RE.search(_live(command, double=True)), 1
            if match is None:
                return command
        body = command[match.start(group):match.end(group)]
        if group == 2:
            body = _BACKTICK_ESCAPE_RE.sub(r"\1", body)
        if not looking(body):
            return None
        word = "SUBST" if match.re is _PROCESS_RE else _SUBST_MARK
        command = command[:match.start()] + word + command[match.end():]


def _segments(command):
    """The parts of a chain, split outside quotes, with harmless redirects dropped.

    None when the command runs an acting command or process substitution, leaves
    one unpaired, or redirects into a file: such a command is never "only
    looking", whatever its parts are.
    """
    command = _unsubstitute(command)
    if command is None:
        return None
    live = _live(command)
    if "$(" in live or "`" in live or "<(" in _live(command, double=True):
        return None
    masked = _QUOTED_RE.sub(lambda m: "Q" * len(m.group(0)), command)
    cleaned = _HARMLESS_REDIRECT_RE.sub(lambda m: " " * len(m.group(0)), masked)
    if ">" in cleaned:
        return None
    parts, position = [], 0
    for match in _SEGMENT_SPLIT_RE.finditer(cleaned):
        parts.append(command[position:match.start()])
        position = match.end()
    parts.append(command[position:])
    return [_HARMLESS_REDIRECT_RE.sub("", part).strip() for part in parts if part.strip()]


#: ``python3 -c '<script>'``: looking only inside the jail, and only a script
#: that names nothing able to write, delete, spawn, reach the network or run
#: code it builds. Models reach for it to read the ledger or a JSON payload;
#: the jail makes a mistake in this list cost a throwaway copy, not the host.
_PYTHON_PART_RE = re.compile(r"^python3?\s+-c\s+")
#: Reading a module's source names it without running anything; a plain
#: ``import`` (no ``as``, no ``from``) binds the name and nothing more. Both are
#: dropped before the script is checked, so ``import subprocess, inspect;
#: print(inspect.getsource(subprocess.call))`` looks, and any other direct use of
#: a module named below still acts. A name looked up at run time never appears
#: as a word, so ``globals(``, ``vars(``, ``sys.modules``, ``getattr(`` and
#: ``__dict__`` act whatever they look up.
_PYTHON_READS_RE = re.compile(
    r"\binspect\.(getsource|getsourcelines|getdoc|signature|getfile|getsourcefile)"
    r"\(\s*[A-Za-z_][\w.]*\s*\)"
    r"|(?<!\w)import\s+[\w.]+(\s*,\s*[\w.]+)*(?!\s*(as\b|[\w.,]))")
_PYTHON_ACTS_RE = re.compile(
    r"\b(shutil|subprocess|socket|urllib|http|requests|ctypes|multiprocessing|importlib|"
    r"tempfile|sqlite3|pty|signal)\b"
    r"|\bfrom\s+os\b|\bos\.(remove|unlink|rmdir|removedirs|rename|renames|replace|system|"
    r"popen|exec\w*|spawn\w*|fork\w*|kill\w*|mkdir|makedirs|chmod|chown|link|symlink|"
    r"truncate|write|open|putenv|unsetenv|chdir|utime|mkfifo|mknod)\b|\bos\.environ\s*\["
    r"|\.(write|writelines|write_text|write_bytes|unlink|rename|replace|mkdir|rmdir|touch|"
    r"chmod|symlink_to|hardlink_to)\s*\("
    r"|\bopen\s*\([^)]*,\s*(mode\s*=\s*)?[rbt]*['\"][^'\"]*[wax+]"
    r"|\b(exec|eval|compile|__import__|breakpoint|input)\s*\("
    r"|\b(globals|vars|getattr)\s*\(|\bsys\.modules\b|__dict__"
)

_TAIL_SPLIT_RE = re.compile(r"\s*(?:&&|\|\||;|\n)\s*")


def chain_parts(command):
    """The commands a chain runs, in order: ``a; b`` and ``a && b`` are two.

    Split where :func:`strip_looking_tail` cuts, outside quotes. Pipes stay: what
    a command is piped into is part of running it.
    """
    masked = _QUOTED_RE.sub(lambda m: "Q" * len(m.group(0)), command)
    parts, position = [], 0
    for cut in _TAIL_SPLIT_RE.finditer(masked):
        parts.append(command[position:cut.start()])
        position = cut.end()
    parts.append(command[position:])
    return [part.strip() for part in parts if part.strip()]


def strip_looking_tail(command):
    """``command`` without trailing parts that only look (``; echo "exit:$?"``).

    A chain's last looking parts change nothing the graded action did, so a
    pattern anchored at the command's end ignores them. Pipes stay: what a
    command is piped into is part of running it. Quotes are masked first, so a
    separator inside a string never splits.
    """
    while True:
        masked = _QUOTED_RE.sub(lambda m: "Q" * len(m.group(0)), command)
        cuts = list(_TAIL_SPLIT_RE.finditer(masked))
        if not cuts:
            return command
        last = cuts[-1]
        head, tail = command[:last.start()], command[last.end():]
        if not head.strip() or (tail.strip() and not looking(tail)):
            return command
        command = head


def looking(command, python=False):
    """True when every part of ``command`` only reads (or is setup).

    ``python`` admits a read-only ``python3 -c`` part; only a jailed sandbox
    passes it, so on the host every such script stays consequential.
    """
    parts = _segments(command)
    if not parts:
        return False
    for part in parts:
        if not _part_looking(part, python):
            return False
    return True


def _ansi_c(body):
    """An ANSI-C ``$'…'`` body as bash 5 decodes it, or None.

    bash's own escapes are read (:data:`_ANSI_C_ESCAPE_RE`); an octal byte is
    masked to eight bits. A backslash pair outside bash's table is kept as the two
    characters typed, as bash keeps it (``\\d`` stays ``\\d``; so do ``\\x``,
    ``\\u`` and ``\\U`` with no hex digit, and ``\\c`` at the end). A decoded
    NUL ends the span, as it ends bash's string: it and the rest of the body are
    dropped (``a\\0b`` is ``a``, and ``-delete\\0x`` is ``-delete``). A code point
    past U+10FFFF, or a non-ASCII character after ``\\c``, returns None: the word
    cannot be read here, so the part that holds it acts. 24-22: IN-02 of the review
    at 329fa95, P-24-62. No codec and no process-wide state is touched, so this is
    safe on the ``--jobs`` thread pool.
    """
    out, position = [], 0
    while True:
        index = body.find("\\", position)
        if index < 0:
            out.append(body[position:])
            return "".join(out)
        out.append(body[position:index])
        match = _ANSI_C_ESCAPE_RE.match(body, index)
        if match is None:
            out.append(body[index:index + 2])
            position = index + 2
            continue
        named, octal, hex_byte, short, wide, control = match.groups()
        if named is not None:
            char = _ANSI_C_NAMED[named]
        elif octal is not None:
            char = chr(int(octal, 8) & 0xFF)
        elif hex_byte is not None:
            char = chr(int(hex_byte, 16))
        elif control is not None:
            if ord(control[0]) > 0x7F:
                return None
            char = "\x7f" if control == "?" else chr(ord(control[0]) & 0x1F)
        else:
            point = int(short if short is not None else wide, 16)
            if point > 0x10FFFF:
                return None
            char = chr(point)
        if char == "\x00":
            return "".join(out)
        out.append(char)
        position = match.end()


def _unquoted(word, live=None, quoted=None):
    """``word`` as the shell passes it on, with its quoting removed, or None.

    A ``'…'`` span is its text; a ``"…"`` or ``$"…"`` span is its text with the
    shell's double-quote escapes undone; a backslash outside quotes yields the
    next character (and with a newline, nothing); a ``$'…'`` span is decoded as
    bash 5 decodes it (:func:`_ansi_c`): an escape outside bash's table kept as
    typed, the span cut at a NUL while the word goes on (``$'a\\0b'c`` is ``ac``),
    and one it cannot read makes the whole word None.

    With ``live``, each whole expansion the shell makes outside quotes (one
    :data:`_EXPANSION_RE` reads: ``$x``, ``${x}``, ``$?``, a backtick) is written as
    ``live``, and each one unescaped inside double quotes as ``quoted``, which is
    ``live`` unless given (24-22: P-24-61; 24-26: CR-02 of the review at aac605a,
    P-24-67). Either may be a function of the expansion's text, as
    :func:`_constant_or_doubt` is for D-30's doubt check (24-32). A ``$'`` or ``$"``
    opener is a quote, not an expansion.
    """
    quoted = live if quoted is None else quoted

    def dquote(match):
        if match.group(1) is not None:
            return "" if match.group(1) == "\n" else match.group(1)
        return _live_marked(match.group(2), quoted)

    out, position = [], 0
    for match in _QUOTE_PIECE_RE.finditer(word):
        out.append(_live_marked(word[position:match.start()], live))
        ansi, single, double, escaped = match.groups()
        if ansi is not None:
            decoded = _ansi_c(ansi)
            if decoded is None:
                return None
            out.append(decoded)
        elif single is not None:
            out.append(single)
        elif double is not None:
            out.append(_DQUOTE_LIVE_RE.sub(dquote, double))
        else:
            out.append("" if escaped == "\n" else escaped)
        position = match.end()
    out.append(_live_marked(word[position:], live))
    return "".join(out)


def _live_marked(bare, live):
    """``bare`` with each whole expansion in it written as ``live``, or as is if None.

    An expansion is one :data:`_EXPANSION_RE` reads, so the mark stands for all of
    ``${x}`` or ``$x``, not its ``$`` alone (24-26: CR-02 of the review at aac605a,
    P-24-67). ``live`` is a string, or a function of the expansion's text.
    """
    if live is None:
        return bare
    return _EXPANSION_RE.sub(
        (lambda match: live(match.group(0))) if callable(live) else (lambda match: live), bare)


#: A part whose command takes a search pattern: any control keywords, an optional
#: ``xargs`` with its options, then ``grep``, ``egrep``, ``fgrep``, ``rg`` or
#: ``git grep`` (``git`` with ``-C <dir>`` and ``--no-pager``), named ``tool``. Only
#: these commands take a pattern or a pattern file where an option could stand,
#: so only their words after ``--``, ``-e`` or ``-f`` are left as typed.
_PATTERN_COMMAND_RE = re.compile(
    r"^(" + _CONTROL_LEAD_RE.pattern[1:] + r")*(" + _XARGS_RE.pattern[1:] + r")?"
    r"(?P<tool>e?grep|fgrep|rg|git(\s+(-C\s+\S+|--no-pager))*\s+grep)(?=\s|$)")
#: The short options each of those commands takes without a value, and those it
#: takes with one. A cluster is read letter by letter: a no-value letter lets the
#: next one be read, and a value-taking letter takes the rest of the cluster as
#: its value, so rg's ``-ge`` is ``-g e`` and ``-re`` is ``-r e``. A letter in
#: neither table cannot be placed, and every later word of the part is then read
#: as the shell passes it (:func:`_options_unquoted`): a letter missing here can
#: make a read act, never an action look. A wrong entry misplaces every word after
#: it, either way, so a letter goes in only as the tool really takes it.
#:
#: Where the tables come from (24-22: IN-08 of the review at 458b1b3). The short
#: and long tables below were read from GNU grep 3.12's ``--help``, ripgrep
#: 15.1.0's ``--help`` and git 2.53.0's ``git grep -h``, and checked by running
#: each entry (24-REVIEW-FIX.md): a no-value entry left the next word free and a
#: value-taking one swallowed it. They are the binaries the jail runs: it binds
#: the host's ``/usr``, and ``grep``, ``rg`` and ``git`` inside it are
#: ``/usr/bin/grep``, ``/usr/bin/rg`` and ``/usr/bin/git``, the same files as on
#: the host. The rule for an entry: an option goes in only as every
#: implementation the jail may bind takes it. An implementation that accepts more
#: letters, as ugrep does (``-Q``), leaves those letters unplaced here, so the
#: words after them are read as the shell passes them; never complete a table
#: from such a tool's ``--help``.
_NO_VALUE_FLAGS = {
    "grep": "0123456789abcEFGHhIiLlnoPqRrsTUVvwxyZz",
    "rg": "0.abcFHhIiLlNnoPpqSsUuVvwxz",
    "git": "acEFGHhIiLlnoPpqrvWwz",
}
_VALUE_FLAGS = {"grep": "ABCDdefm", "rg": "ABCdEefgjMmrTt", "git": "ABCefm"}
#: The long options each command takes without a value, and those that take the
#: next word as theirs, by exact name. One written with ``=`` carries its value.
#: Any other (an abbreviation, an unlisted ``--no-`` form) cannot be placed, as a
#: letter in neither table cannot, with the same rule for what goes in.
_NO_VALUE_LONG = {
    "grep": frozenset("""
        --basic-regexp --byte-offset --color --colour --count --dereference-recursive
        --extended-regexp --files-with-matches --files-without-match --fixed-strings
        --ignore-case --initial-tab --invert-match --line-buffered --line-number
        --line-regexp --no-filename --no-messages --null --only-matching --perl-regexp
        --quiet --recursive --silent --text --with-filename --word-regexp""".split()),
    "rg": frozenset("""
        --byte-offset --case-sensitive --column --count --count-matches
        --files-with-matches --files-without-match --fixed-strings --follow --heading
        --hidden --ignore-case --invert-match --json --line-number --line-regexp
        --multiline --no-config --no-filename --no-heading --no-ignore --no-ignore-vcs
        --no-line-number --no-messages --null --only-matching --passthru --pcre2 --pretty
        --quiet --search-zip --smart-case --stats --text --trim --unrestricted --vimgrep
        --with-filename --word-regexp""".split()),
    "git": frozenset("""
        --all-match --and --basic-regexp --break --cached --color --column --count
        --exclude-standard --extended-regexp --files-with-matches --files-without-match
        --fixed-strings --full-name --function-context --heading --ignore-case --index
        --invert-match --line-number --name-only --no-color --no-index --not --null
        --only-matching --or --perl-regexp --quiet --recurse-submodules --recursive
        --show-function --text --textconv --untracked --word-regexp""".split()),
}
_VALUE_LONG = {
    "grep": frozenset("""
        --after-context --before-context --binary-files --context --devices --directories
        --exclude --exclude-dir --exclude-from --include --label --max-count""".split()),
    "rg": frozenset("""
        --after-context --before-context --color --colors --context --context-separator
        --dfa-size-limit --encoding --engine --field-context-separator
        --field-match-separator --generate --glob --hostname-bin --hyperlink-format
        --iglob --ignore-file --max-columns --max-count --max-depth --max-filesize
        --path-separator --pre --pre-glob --regex-size-limit --replace --sort --sortr
        --threads --type --type-add --type-clear --type-not""".split()),
    "git": frozenset("""
        --after-context --before-context --context --max-count --max-depth
        --threads""".split()),
}


def _next_word(option, tool):
    """What ``option`` makes of the next word, or None when it leaves that word free.

    A bare ``--`` makes every later word an operand (``"rest"``). ``-e``, ``-f``,
    ``--regexp``, ``--file`` and a cluster of no-value letters ending in ``e`` or
    ``f`` make it a pattern or a pattern file (``"pattern"``). A value-taking long
    option, or a cluster whose last letter takes a value, takes it as that value
    (``"value"``), so it names nothing (``rg -g -e …`` searches the glob ``-e``). A
    value-taking letter before the last carries its value attached, and the next
    word is free, as it is after a no-value option or a long option with ``=``. An
    option ``tool`` is not known to take either way cannot be placed
    (``"unplaced"``).
    """
    if option == "--":
        return "rest"
    if option in ("--regexp", "--file"):
        return "pattern"
    if option.startswith("--"):
        if "=" in option or option in _NO_VALUE_LONG[tool]:
            return None
        return "value" if option in _VALUE_LONG[tool] else "unplaced"
    if not option.startswith("-"):
        return None
    for index, letter in enumerate(option[1:], 2):
        if letter in _NO_VALUE_FLAGS[tool]:
            continue
        if letter not in _VALUE_FLAGS[tool]:
            return "unplaced"
        if index < len(option):
            return None
        return "pattern" if letter in "ef" else "value"
    return None


#: D-30's one list of commands in which doubt still looks. Each has no option, in any
#: implementation the jail may bind (``/usr/bin/<name>`` or the bash builtin), that
#: writes a file or runs a program, and places no option value the kit reads to decide
#: a look, so whatever word an expansion builds there, the part only reads. A name
#: goes in only after that ``--help`` check and with a looking context in the
#: expansion cross product (``tests/test_evals.py``), which fails for a name without
#: one. ``mkdir`` is the exception: it has no context, and it looks only through
#: :data:`_SETUP_PART_RE`'s shape. Every other command (``find``, ``sort``, ``tree``,
#: ``sed``, ``awk``, ``xargs``, ``env``, ``rg``, ``git``, ``crayon``, ``python3`` and
#: anything not named) is read as having an acting option or a placed value, so doubt
#: there acts (24-32: D-30, CR-05 and CR-06 of the review at 802e0e3).
_DOUBT_LOOKS_COMMANDS = ("cat", "cd", "echo", "egrep", "fgrep", "grep", "head", "ls", "mkdir",
                         "printf", "pwd", "tail", "test", "true", "wc", ":", "[")
#: A part's command word on that list, or a bare assignment (``NAME=word`` and nothing
#: after it), which runs no command. Built from the tuple, its one definition site.
_DOUBT_LOOKS_RE = re.compile(
    r"^(?:(?:" + "|".join(re.escape(name) for name in _DOUBT_LOOKS_COMMANDS) + r")(?=\s|$)"
    r"|[A-Za-z_][A-Za-z0-9_]*=\S*$)")


def _doubt_is_harmless(part):
    """True when doubt in ``part`` leaves it looking: it runs a listed command, or none.

    Its control keywords are peeled first (:func:`_command_word_first`). A part that is
    only control keywords (``for f in $x``, ``case "$f" in``) runs no command, and
    neither does a bare assignment; any other part is harmless only when its command
    is on :data:`_DOUBT_LOOKS_COMMANDS` (24-32: D-30).
    """
    command = _command_word_first(part)
    return not command or bool(_DOUBT_LOOKS_RE.match(command))


def _constant_or_doubt(text):
    """``"0"`` for an expansion the kit reads as constant, else :data:`_LIVE_MARK`.

    Only ``$?``, ``$#`` and ``$$`` are constant (:data:`_CONSTANT_EXPANSION_RE`), and
    each builds digits. Every other expansion is doubt, a lone ``$``, a backtick and
    :data:`_SUBST_MARK` included (24-32: D-30). It is called only for an expansion
    inside double quotes, where no ``IFS`` splits those digits; a bare one is doubt
    before it gets here (24-35: CR-08 of the review at 5fdfe1b).
    """
    return "0" if _CONSTANT_EXPANSION_RE.fullmatch(text) else _LIVE_MARK


def _options_unquoted(part):
    """``part`` with each word the shell passes on as an option written bare, or None.

    A quoted or escaped option (``sed '-i'``, ``find . "-delete"``) is checked
    as if typed bare, because the shell hands the program the same word. A space
    inside an option word (``awk -F' '``, ``sort '-o out'``) is kept as NUL, a
    character that is neither a space nor a word character: the word stays one
    word, and a word boundary after the option's name still holds. For grep,
    egrep, fgrep, rg and git grep, a word after a bare ``--`` and the word after
    ``-e``, ``-f``, ``--regexp`` or ``--file`` is a pattern or a pattern file,
    never an option, so it keeps its quotes (:func:`_next_word` says which words
    those are); so does every word that does not start with ``-`` (a sed script,
    an awk program). After an option the tool's tables cannot place, no later word
    of the part keeps its quotes. In an option word written bare, each whole
    expansion the shell makes is :data:`_LIVE_MARK` (24-22: P-24-61).

    D-30's doubt check comes first, for each word holding an expansion, a kept
    pattern word too (24-32: D-30, CR-05 and CR-06 of the review at 802e0e3). The word
    is read with each bare expansion as doubt, a ``$?``, ``$#`` or ``$$`` among them,
    since a looking part may set ``IFS`` to split its digits, and with each expansion
    inside double quotes as :func:`_constant_or_doubt` makes it (24-35: CR-08 of the
    review at 5fdfe1b). If any is doubt, the shell, not the typed text, decides which
    words bash builds there and which option takes one, so the part returns None unless
    its command is harmless (:func:`_doubt_is_harmless`). In a harmless part the word
    is kept, and at or after the pattern position every later word is read as the
    shell passes it, since which one names a pattern cannot be told. A word whose
    every expansion is a quoted constant is placed by the text it builds (``"$?"`` is
    ``0``): only inside double quotes is no field splitting applied. An ANSI-C ``$'…'``
    word that cannot be read returns None, and the part is acting: doubt stays
    acting. The result is for classification only; nothing runs or is graded from it.
    """
    harmless = _doubt_is_harmless(part)
    command = _PATTERN_COMMAND_RE.match(part)
    patterns_from = command.end() if command else len(part) + 1
    tool = command.group("tool") if command else ""
    tool = "rg" if tool == "rg" else "git" if tool[:3] == "git" else "grep"
    out, position, keep_next, keep_rest, taken, unplaced = [], 0, False, False, False, False
    for match in _WORD_RE.finditer(part):
        word = match.group(0)
        out.append(part[position:match.start()])
        position = match.end()
        # The same word, each whole expansion the shell makes marked, so an
        # attached sed script (-e"$p") is told from a quoted one (-e'$p').
        marked = _unquoted(word, live=_LIVE_MARK)
        kept = match.start() >= patterns_from and (keep_rest or keep_next)
        built = None
        if marked is not None and _LIVE_MARK in marked:
            built = _unquoted(word, live=_LIVE_MARK, quoted=_constant_or_doubt)
            if built is None or _LIVE_MARK in built:
                if not harmless:
                    return None
                built = None
                if match.start() >= patterns_from:
                    unplaced = True
        if kept:
            out.append(word)
            keep_next = False
            continue
        bare = _unquoted(word)
        if bare is None:
            return None
        if match.start() >= patterns_from and not unplaced:
            # A word an option took as its value names nothing. Once an option
            # cannot be placed, which later word names a pattern is unknown, so
            # every one is read as the shell passes it: doubt stays acting.
            after = None if taken else _next_word(bare if built is None else built, tool)
            unplaced = after == "unplaced"
            keep_rest, keep_next, taken = (after == "rest", after == "pattern",
                                           after == "value")
        if bare.startswith("-"):
            out.append(re.sub(r"\s", "\x00", marked))
        else:
            out.append(word)
    out.append(part[position:])
    return "".join(out)


def _acting_word(part):
    """True when ``part`` holds an acting word, as typed or with each expansion gone.

    With the mark removed, an option whose attached value is an expansion is read
    as the option alone: ``-delete"$x"`` reads as ``-delete`` and ``--pre"$x"=sh`` as
    ``--pre=sh`` (24-26: CR-02 of the review at aac605a, P-24-68). This second reading
    only ever adds an acting verdict; D-30's doubt check has already made such a
    part act unless its command is harmless (24-32: :func:`_doubt_is_harmless`).
    """
    return bool(_ACTING_WORD_RE.search(part)
                or _ACTING_WORD_RE.search(part.replace(_LIVE_MARK, "")))


def _part_looking(part, python):
    """True when one part of a chain only reads; what ``xargs`` runs is a part too.

    The acting words are checked again once the control keywords are peeled off,
    so ``then sed -i …`` or ``do rg --pre …`` acts as the bare command does.
    Behind ``xargs``, a ``uniq`` or ``xxd`` acts: xargs appends operands, and a
    second operand is a file it writes. Its options are read unquoted
    (:func:`_options_unquoted`), once, before every check: a part with a word that
    holds any expansion but a ``$?``, ``$#`` or ``$$`` inside double quotes acts
    unless its command is on :data:`_DOUBT_LOOKS_COMMANDS` (24-32: D-30, CR-05 and
    CR-06 of the review at 802e0e3; 24-35: CR-08 of the review at 5fdfe1b, since bare
    they split on an ``IFS`` a looking part set). Both acting-word checks also read
    the part with every expansion gone (:func:`_acting_word`), so an option whose
    attached value is an expansion acts as the option alone (24-26: CR-02 of the
    review at aac605a, P-24-68).
    """
    part = _options_unquoted(part)
    if part is None:
        return False
    behind_xargs = False
    while True:
        if _acting_word(part):
            return False
        part = _command_word_first(part)
        if not part:
            return True
        if _acting_word(part):
            return False
        if python and _PYTHON_PART_RE.match(part):
            return not _PYTHON_ACTS_RE.search(_PYTHON_READS_RE.sub("READ", part))
        xargs = _XARGS_RE.match(part)
        if xargs:
            part = part[xargs.end():]
            behind_xargs = True
            continue
        if behind_xargs and _XARGS_NEVER_RE.match(part):
            return False
        if _SED_RE.match(part):
            return _sed_reads(part)
        if _AWK_RE.match(part):
            awk = _AWK_LOOKS_RE.match(part)
            return bool(awk) and not _AWK_PROGRAM_ACTS_RE.search(awk.group(4))
        return bool(_INSPECT_RE.match(part) or _GIT_BRANCH_LISTS_RE.match(part)
                    or _UNIQ_LOOKS_RE.match(part) or _XXD_LOOKS_RE.match(part)
                    or _ENV_BARE_RE.match(part) or _READONLY_CRAYON_RE.match(normalise(part))
                    or _SETUP_PART_RE.match(part))


def _sed_reads(part):
    """True when a ``sed`` part only reads and prints.

    ``sed --help`` and ``sed --version`` alone look. Otherwise every option must
    be a reading one (``-n``, ``-E``, ``-r``, ``-s``, ``-u``, ``-z``, ``--debug`` or
    the long names) or give a script: ``-e`` or ``--expression``, with the script
    as the next word or attached (``-eSCRIPT``, ``--expression=SCRIPT``). A bare
    ``--`` ends the options. When no option gave a script, the first operand is
    the script; every other operand is a file. A script word is read after its
    quoting is removed (``'$p'``, ``"\\$p"`` and ``$'1p'`` are each ``$p`` or
    ``1p``), unless it holds a ``$`` or backtick the shell expands
    (:func:`_sed_script_text`). An attached script has already lost its quoting
    in :func:`_options_unquoted`, which writes each such ``$`` or backtick as
    :data:`_LIVE_MARK`; a script holding the mark is never read (24-22: P-24-61,
    of the two mechanisms planned, the mark, since the typed text and the
    rewritten one cannot always be lined up). Each script may hold only what
    :data:`_SED_SCRIPT_READS_RE` reads: addresses (``/regexp/`` and
    ``\\cregexpc``) and ranges, ``!``, braces, the commands ``p = l q d n N D P g
    G h H x z F Q``, ``b``, ``t`` and ``T`` with a label, ``:label``, and ``s``
    with the flags ``g``, ``p``, ``i``, ``I``, ``m``, ``M`` or a number, a bracket
    expression in a regex read as sed reads it (24-22: WR-03 of the review at
    329fa95, P-24-60). Anything else acts: ``-i``, ``--in-place``, ``-f``, ``-l``,
    ``--follow-symlinks`` or any other option, ``w``, ``W``, ``e``, ``r``, ``R``,
    ``y``, ``a``, ``i``, ``c`` or any other command or flag, no script at all, and
    a script this cannot read.
    """
    words = [match.group(0) for match in _WORD_RE.finditer(part)][1:]
    if words in (["--help"], ["--version"]):
        return True
    scripts, operands, index, options = [], [], 0, True
    while index < len(words):
        word = words[index]
        index += 1
        if not options or word == "-" or not word.startswith("-"):
            operands.append(word)
        elif word == "--":
            options = False
        elif not _SED_FLAG_RE.match(word):
            expression = _SED_EXPRESSION_RE.match(word)
            if expression is None:
                return False
            if expression.group(3) or expression.group(2) == "=":
                attached = expression.group(3).replace("\x00", " ")
                if _LIVE_MARK in attached:
                    return False
                scripts.append(attached)
            elif index < len(words):
                scripts.append(_sed_script_text(words[index]))
                index += 1
            else:
                return False
    if not scripts:
        if not operands:
            return False
        scripts.append(_sed_script_text(operands[0]))
    return all(script is not None and _SED_SCRIPT_READS_RE.match(script)
               for script in scripts)


def _sed_script_text(word):
    """The script a typed ``sed`` script word passes on, or None if the shell may change it.

    The word's quoting is removed as the shell removes it (:func:`_unquoted`). A
    ``$`` or backtick the shell expands, bare or unescaped inside double quotes,
    means the shell decides the script, so None; a ``$'...'`` or ``$"..."`` opener
    is a quote, not an expansion.
    """
    text = _unquoted(word, live=_LIVE_MARK)
    if text is None or _LIVE_MARK in text:
        return None
    return text


def _command_word_first(part):
    """``part`` with its control-flow keywords peeled off; "" if it is only those."""
    while True:
        part = part.strip().rstrip(";").strip()
        if not part or _CONTROL_WHOLE_RE.match(part):
            return ""
        peeled = _CONTROL_LEAD_RE.sub("", part, count=1)
        peeled = _CASE_PATTERN_RE.sub("", peeled, count=1) if peeled == part else peeled
        if peeled == part:
            return part
        part = peeled


def normalise(command):
    """A command as typed, minus what does not change its meaning here.

    Quotes are dropped, whitespace collapsed, and a trailing ``2>&1`` removed,
    so ``crayon show "cfg" --json 2>&1`` matches ``crayon show cfg --json``.
    """
    command = re.sub(r"\s*2>&1\s*$", "", command.strip())
    command = command.replace('"', "").replace("'", "")
    return re.sub(r"\s+", " ", command).strip()


def tools_for(skill):
    """The tool definitions ``skill`` declares, in its declared order."""
    return [
        {"type": "function",
         "function": dict({"name": name}, **TOOL_SCHEMAS[name])}
        for name in skill.tools if name in TOOL_SCHEMAS
    ]


def arguments(call):
    try:
        parsed = json.loads(call.get("arguments") or "{}")
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def render_output(output, exit_code):
    """What a shell tool shows: the output, then a non-zero exit code."""
    text = output if output else "(no output)"
    if exit_code:
        text += "\n(exit code %d)" % exit_code
    return text


class Jail(object):
    """Where a model's looking command runs: a bubblewrap jail of one sandbox.

    The command sees the sandbox copy at the real ``WORKDIR`` and each sibling
    of it (the throwaway home, a docs root moved beside the repository) at
    ``/srv/<name>``; ``/usr`` read-only, a ``crayon`` shim on ``/opt/crayon``, an
    empty ``/tmp``, its own process table, and no network. Nothing else of the
    machine running the eval exists in there — not its home, not the checkout
    the eval runs from — so a command that goes looking beyond the repository
    finds nothing to show a model.
    """

    SHIM = "/opt/crayon/bin"
    PATH = SHIM + ":/usr/local/bin:/usr/bin:/bin"

    def __init__(self, shim_dir, crayon_py, bwrap="bwrap"):
        self.shim_dir = str(shim_dir)
        self.crayon_py = str(crayon_py)
        self.bwrap = bwrap

    def argv(self, root, env, command):
        args = [self.bwrap, "--unshare-all", "--die-with-parent", "--new-session",
                "--ro-bind", "/usr", "/usr"]
        for top in ("/bin", "/lib", "/lib64", "/sbin"):
            if os.path.islink(top):
                args += ["--symlink", os.readlink(top), top]
            elif os.path.isdir(top):
                args += ["--ro-bind", top, top]
        for kept in ("/etc/ld.so.cache", "/etc/alternatives", "/etc/localtime"):
            args += ["--ro-bind-try", kept, kept]
        args += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
                 "--ro-bind", self.shim_dir, self.SHIM,
                 "--ro-bind", self.crayon_py, "/opt/crayon/crayon.py"]
        holder = os.path.dirname(root)
        for name in sorted(os.listdir(holder)):
            full = os.path.join(holder, name)
            if full == root:
                args += ["--bind", full, WORKDIR]
            elif name != os.path.basename(WORKDIR):
                args += ["--bind", full, "/srv/" + name]
        args += ["--chdir", WORKDIR, "--clearenv"]
        for key, value in sorted(env.items()):
            args += ["--setenv", key, value]
        return args + ["bash", "-c", command]


class SandboxRepo(object):
    """A real copy of a recorded state, in which only looking is carried out.

    The copy lives at ``root``; the model is told it works in ``WORKDIR``, and
    paths are mapped both ways. ``Read``/``Glob``/``Grep`` read the copy. A
    ``Bash`` call that only looks (``looking``) runs for real, in the copy,
    under a constructed environment: ``PATH`` with a ``crayon`` shim first, a
    throwaway ``HOME``, git's global and system config switched off, and
    nothing inherited, so no key or setting of the machine running the eval can
    reach a model's command. With a ``jail`` (:class:`Jail`) it runs inside it,
    where nothing of the machine but ``/usr`` exists; without one it runs on
    the host, which only a replay of fixed commands may do (``lanes.run_b``
    refuses a live model that). ``overrides`` answer a command from the replayed
    history instead, where the history was written rather than recorded (a
    refusal no real state here would print). Anything else is consequential:
    it ends the episode and is never run.
    """

    def __init__(self, root, bin_dir, overrides=(), timeout=20, limit=20000, jail=None):
        self.root = os.path.realpath(str(root))
        self.jail = jail
        self.overrides = list(overrides)
        self.timeout = timeout
        self.limit = limit
        home = os.path.join(os.path.dirname(self.root), "home")
        if not os.path.isdir(home):
            os.makedirs(home)
        self.env = {
            "PATH": Jail.PATH if jail else "%s:/usr/local/bin:/usr/bin:/bin" % bin_dir,
            "HOME": "/srv/home" if jail else home,
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
            "GIT_PAGER": "cat",
            "PAGER": "cat",
            "TERM": "dumb",
        }

    # -- paths ----------------------------------------------------------------

    def _to_disk(self, text):
        return (text or "").replace(WORKDIR, self.root)

    def _from_disk(self, text):
        return (text or "").replace(self.root, WORKDIR)

    def _inside(self, path):
        """The real path for a model's path, or None outside the repository."""
        path = self._to_disk((path or "").strip()) or "."
        full = os.path.realpath(os.path.join(self.root, path))
        if full != self.root and not full.startswith(self.root + os.sep):
            return None
        return full

    def _shown(self, full):
        return os.path.relpath(full, self.root)

    # -- the read tools -------------------------------------------------------

    @staticmethod
    def _not_text(args, *keys):
        """A tool error for the first of ``keys`` given but not a string, else None.

        A model's argument of the wrong type is answered the way a harness answers
        it, as a tool error the model sees, never raised out of the sweep (24-30,
        WR-17 of the review at 1ba4892). An absent or null argument takes its
        default. A string holding a NUL byte, which the OS refuses in a path, is
        answered the same way (24-33, WR-21 of the review at 802e0e3).
        """
        for key in keys:
            if args.get(key) is not None and not isinstance(args[key], str):
                return "Error: %s must be a string" % key
            if "\x00" in (args.get(key) or ""):
                return "Error: %s must not contain a NUL byte" % key
        return None

    def read(self, args):
        wrong = self._not_text(args, "file_path")
        if wrong:
            return wrong
        full = self._inside(args.get("file_path", ""))
        if full is None:
            return "Error: %s is outside the repository" % args.get("file_path")
        if not os.path.isfile(full):
            return "Error: file not found: %s" % args.get("file_path")
        with open(full, encoding="utf-8", errors="replace") as handle:
            lines = handle.read().split("\n")
        try:
            offset = max(int(args.get("offset") or 1), 1) - 1
            limit = int(args.get("limit") or len(lines))
        except (TypeError, ValueError, OverflowError):
            return "Error: offset and limit must be integers"
        return "\n".join(lines[offset: offset + limit])[: self.limit]

    def _files(self, base):
        for directory, dirs, files in os.walk(base):
            dirs[:] = sorted(d for d in dirs if d != ".git")
            for name in sorted(files):
                yield os.path.join(directory, name)

    def glob(self, args):
        wrong = self._not_text(args, "pattern", "path")
        if wrong:
            return wrong
        base = self._inside(args.get("path", "")) or self.root
        pattern = "*" if args.get("pattern") is None else args["pattern"]
        hits = []
        for full in self._files(base):
            rel = os.path.relpath(full, base)
            if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(rel, pattern.replace("**/", "")):
                hits.append(self._shown(full))
        return "\n".join(hits[:500]) or "(no matches)"

    def grep(self, args):
        wrong = self._not_text(args, "pattern", "path", "glob")
        if wrong:
            return wrong
        try:
            pattern = re.compile(args.get("pattern") or "")
        except (re.error, RecursionError, OverflowError) as exc:
            return "Error: bad pattern: %s" % exc
        base = self._inside(args.get("path", "")) or self.root
        targets = [base] if os.path.isfile(base) else self._files(base)
        out = []
        for full in targets:
            if args.get("glob") and not fnmatch.fnmatch(os.path.basename(full), args["glob"]):
                continue
            try:
                with open(full, encoding="utf-8") as handle:
                    for number, line in enumerate(handle, 1):
                        if pattern.search(line):
                            out.append("%s:%d:%s" % (self._shown(full), number, line.rstrip("\n")))
            except (UnicodeDecodeError, OSError):
                continue
        return "\n".join(out[:200]) or "(no matches)"

    # -- the shell ------------------------------------------------------------

    def bash(self, command):
        """(output, exit) for a command carried out or answered here, else None.

        A ``command`` that is not a string is answered as a usage error (24-30,
        WR-17), so ``normalise`` and ``looking`` only ever read text. So is one
        holding a NUL byte, which no process can be given (24-33, WR-21 of the
        review at 802e0e3).
        """
        if not isinstance(command, str):
            return "Error: command must be a string", 2
        if "\x00" in command:
            return "Error: command must not contain a NUL byte", 2
        normal = normalise(command)
        for override in self.overrides:
            if normal == override.get("exact") or (
                    override.get("prefix") and (normal == override["prefix"]
                                                or normal.startswith(override["prefix"] + " "))):
                return override["output"], override["exit"]
        if not looking(command, python=self.jail is not None):
            return None
        if self.jail:
            argv, env = self.jail.argv(self.root, self.env, command), {}
        else:
            argv, env = ["bash", "-c", self._to_disk(command)], self.env
        try:
            done = subprocess.run(
                argv, cwd=self.root, env=env,
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            return "(timed out after %ds)" % self.timeout, 124
        text = done.stdout.decode("utf-8", "replace")[: self.limit].rstrip("\n")
        return (text if self.jail else self._from_disk(text)), done.returncode

    def serve(self, call):
        """(result text, consequential?) for one tool call."""
        name, args = call["name"], arguments(call)
        if name == "Read":
            return self.read(args), False
        if name == "Glob":
            return self.glob(args), False
        if name == "Grep":
            return self.grep(args), False
        if name == "Bash":
            answered = self.bash(args.get("command", ""))
            if answered is not None:
                return render_output(*answered), False
        return None, True

    def write(self, path, content):
        """Materialise a write the replayed history says already happened."""
        full = self._inside(path)
        if full is None:
            raise ValueError("a history write escapes the repository: %s" % path)
        directory = os.path.dirname(full)
        if not os.path.isdir(directory):
            os.makedirs(directory)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(content)


def history_messages(steps, prefix="h"):
    """Resolved steps -> the assistant/tool/user messages that replay them.

    A step is ``{"user": text}``, ``{"assistant": text}``, a shell step
    ``{"cmd", "exit", "output"}``, or any other tool call
    ``{"call": {"name", "arguments"}, "result": text}``. Call ids are the
    prefix and the step's index, so two replays with different prefixes (a
    prelude's ``p``, a history's ``h``) never pair a result with the wrong call.
    """
    messages = []
    for index, step in enumerate(steps):
        if "user" in step:
            messages.append({"role": "user", "content": step["user"]})
            continue
        if "assistant" in step:
            messages.append({"role": "assistant", "content": step["assistant"]})
            continue
        if "call" in step:
            name, args, result = step["call"]["name"], step["call"]["arguments"], step["result"]
        else:
            name, args = "Bash", {"command": step["cmd"]}
            result = render_output(step["output"], step["exit"])
        call_id = "%s%d" % (prefix, index)
        messages.append({
            "role": "assistant",
            "content": step.get("say", ""),
            "tool_calls": [{"id": call_id, "type": "function",
                            "function": {"name": name, "arguments": json.dumps(args)}}],
        })
        messages.append({"role": "tool", "tool_call_id": call_id, "content": result})
    return messages


def assistant_message(turn):
    message = {"role": "assistant", "content": turn["content"] or ""}
    if turn["tool_calls"]:
        message["tool_calls"] = [
            {"id": call["id"], "type": "function",
             "function": {"name": call["name"], "arguments": call["arguments"]}}
            for call in turn["tool_calls"]
        ]
    return message


def run_episode(provider, spec, messages, tools, repo, max_turns=6, cache=True,
                scope=None):
    """Live turns until the first consequential action (or ``max_turns``).

    Returns a trace: ``turns`` (every live turn), ``decisive`` (what ended the
    episode: ``{"type": "call", "call": ...}``, ``{"type": "text"}`` or
    ``{"type": "none"}`` when the turn cap was reached), ``served`` (the
    looking the model did on the way) and ``retries`` (D-24: how many empty
    turns were re-sent, once each and uncached).

    Any exception from the provider or a tool leaves as a ``ProviderError`` or a
    ``BudgetExceeded`` carrying the cost of the turns already held (``carry_cost``),
    so the case's record keeps them (24-36, WR-24 of the review at 5fdfe1b).
    """
    messages = list(messages)
    turns, served = [], []
    served_ids = []
    retries = 0
    offered = [tool["function"]["name"] for tool in tools or ()]
    for _ in range(max_turns):
        try:
            turn = provider.complete(spec, messages, tools=tools, cache=cache, scope=scope)
            turn, retried = retry_empty_turn(provider, turn, spec, messages, tools=tools,
                                             scope=scope)
        except Exception as exc:
            # The turns already held reach no record with this error or stop; it
            # carries their cost on, so the record still counts it (24-23, WR-02;
            # 24-27, WR-11; 24-36, WR-24 of the review at 5fdfe1b).
            raise carry_cost(exc, sum(held["usage"]["cost"] for held in turns))
        retries += retried
        turns.append(turn)
        if not turn["tool_calls"]:
            return {"turns": turns, "decisive": {"type": "text"}, "served": served,
                    "served_ids": served_ids, "retries": retries}
        messages.append(assistant_message(turn))
        for call in turn["tool_calls"]:
            if call["name"] not in TOOL_SCHEMAS:
                # A name no tool has (a mangled `Bogen`) is answered the way a
                # harness answers it, and the model goes on; it acted on nothing.
                result = "Error: no tool named %r; the tools are: %s" % (
                    call["name"], ", ".join(offered))
                messages.append({"role": "tool", "tool_call_id": call["id"],
                                 "content": result})
                continue
            try:
                result, consequential = repo.serve(call)
            except Exception as exc:
                # The turns held, this one included, carry on with the error (24-36,
                # WR-24 of the review at 5fdfe1b).
                raise carry_cost(exc, sum(held["usage"]["cost"] for held in turns))
            if consequential:
                return {"turns": turns, "decisive": {"type": "call", "call": call},
                        "served": served, "served_ids": served_ids, "retries": retries}
            served.append({"name": call["name"], "arguments": call["arguments"]})
            served_ids.append(call["id"])
            messages.append({"role": "tool", "tool_call_id": call["id"],
                             "content": result})
    return {"turns": turns, "decisive": {"type": "none"}, "served": served,
            "served_ids": served_ids, "retries": retries}
