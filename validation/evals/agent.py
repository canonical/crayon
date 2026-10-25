"""The neutral agent surface: seven tools, a replayed history, a decisive action.

Dev-time evaluation material. Every model sees the same tools, and the tools
carry the names the skills declare in their ``allowed-tools`` frontmatter
(``Read``, ``Bash``, ``Glob``, ``Grep``, ``Write``, ``Edit``,
``AskUserQuestion``), with plain JSON-schema parameters. A model is offered only
the tools its invoked skill declares.

Lane B uses ``run_episode``: the conversation up to a recorded ``crayon`` output
is replayed as real tool calls and results, then the model acts in a real copy
of the recorded state (``Repo``). Reads, searches and commands run there for
real, and the episode goes on while nothing changes. The first call that would
change something ends the episode and is what the case grades:

- ``Write``, ``Edit``, a question to the author (``AskUserQuestion``), or a turn
  with no tool call;
- a command that names a ``crayon`` verb that records (``MUTATING_RE``); it is
  not run;
- any other command after which the copy's files or git index differ from
  before it (``digest.tree``); its output is not shown to the model.

The kit decides by what a command changed, not by predicting what a shell
command will do: the copy runs in a sandbox that holds nothing else and is
thrown away after the case (``sandbox.WorkshopRunner``).
"""

import fnmatch
import json
import os
import re

from openrouter import carry_cost, retry_empty_turn

#: Where the model is told the repository is.
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

#: A ``crayon`` verb that records anything (``resume --dry-run`` only looks),
#: through the shim or the file. The one definition site: ``lanes.MACROS``
#: names it as ``@MUTATING``, so the episode rule and the cases read the same.
MUTATING_PATTERN = (r"\bcrayon(\.py)?\s+(unit\s+(new|edit|retire)|context\s+(stage|record)|"
                    r"signoff|steer|plan-steps|step|draft|edits|review|"
                    r"resume(?![^\n]*--dry-run))\b")
MUTATING_RE = re.compile(MUTATING_PATTERN)


def mutating(command):
    """True when ``command`` names a ``crayon`` verb that records, anywhere in it."""
    return bool(MUTATING_RE.search(command))


# --- reading a command for grading --------------------------------------------
#
# Grading compares a command with a case's pattern. A leading ``cd`` into the
# working directory and trailing parts that only read (``; echo "exit:$?"``,
# ``&& crayon show cfg``) are not the graded action, so they are dropped first.
# These helpers decide nothing about running a command: the sandbox does that by
# what the command changed.

#: ``crayon`` calls that only read.
_READONLY_CRAYON_RE = re.compile(
    r"^crayon(\s+(version|show|summary|verify|context\s+show|resume\s+\S+\s+--dry-run"
    r"|[a-z-]+(\s+[a-z-]+)?\s+(--help|-h))\b|\s+(--help|-h|--version)\b)"
)
#: Shell commands that read.
_INSPECT_RE = re.compile(
    r"^(cat|ls|head|tail|grep|egrep|fgrep|rg|find|wc|pwd|echo|printf|cd|tree|file|stat|"
    r"sort|cut|tr|true|:|test|\[|which|type|command\s+-v|sha256sum|md5sum|du|diff|"
    r"basename|dirname|realpath|readlink|nl|jq|column|od|hexdump|strings|cmp|comm|"
    r"fold|fmt|rev|printenv|id|whoami|uname|date|sleep|"
    r"git(\s+(-C\s+\S+|--no-pager))*\s+(status|log|diff|show|ls-files|ls-tree|rev-parse|"
    r"blame|grep|check-ignore|branch(\s+--show-current)?))(?=\s|$)"
)
#: Setup: naming a variable, or creating a directory under the staging tree.
_SETUP_PART_RE = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_]*=\S*|mkdir\s+-p\s+((/srv/toyq/)?\.crayon/staging/\S+|"
    r"\$\{?[A-Za-z_]\S*))$")
#: What a part may do and still only read: no redirect into a file, no command or
#: process substitution, no ``find`` action.
_ACTS_RE = re.compile(r">|<\(|\$\(|`|-exec\b|-delete\b|-ok\b")
_HARMLESS_REDIRECT_RE = re.compile(r"\d?>\s*/dev/null|\d?>&\d|&>\s*/dev/null")
#: A quoted word, whose separators never split a chain.
_QUOTED_RE = re.compile(r"\$'(?:\\.|[^'\\])*'|'[^']*'|\"(?:\\.|[^\"\\])*\"")
_TAIL_SPLIT_RE = re.compile(r"\s*(?:&&|\|\||;|\n)\s*")
_PIPE_SPLIT_RE = re.compile(r"\s*\|\s*")


def _masked(command):
    return _QUOTED_RE.sub(lambda m: "Q" * len(m.group(0)), command)


def _split(command, pattern):
    masked = _masked(command)
    parts, position = [], 0
    for cut in pattern.finditer(masked):
        parts.append(command[position:cut.start()])
        position = cut.end()
    parts.append(command[position:])
    return [part.strip() for part in parts if part.strip()]


def chain_parts(command):
    """The commands a chain runs, in order: ``a; b`` and ``a && b`` are two.

    Split outside quotes. Pipes stay: what a command is piped into is part of
    running it.
    """
    return _split(command, _TAIL_SPLIT_RE)


#: ``awk`` reads unless its program runs a command, writes a file or reads one
#: through ``getline``; ``sort`` writes with ``-o``, quoted or not.
_AWK_RE = re.compile(r"^g?awk(\s|$)")
_AWK_ACTS_RE = re.compile(r"system\s*\(|getline|>|\||fflush|close\s*\(|inplace")
_SORT_WRITES_RE = re.compile(r"^sort\b.*?(?:^|\s)['\"]?(-o|--output)")


def reads(part):
    """True when one chain part only reads, as grading counts it.

    Every stage of a pipe must read, and nothing may be redirected into a file.
    """
    cleaned = _HARMLESS_REDIRECT_RE.sub("", part).strip()
    if not cleaned or _ACTS_RE.search(_masked(cleaned)):
        return False
    for stage in _split(cleaned, _PIPE_SPLIT_RE):
        if _AWK_RE.match(stage):
            if _AWK_ACTS_RE.search(stage):
                return False
            continue
        if _SORT_WRITES_RE.search(stage):
            return False
        if not (_READONLY_CRAYON_RE.match(stage) or _INSPECT_RE.match(stage)
                or _SETUP_PART_RE.match(stage)):
            return False
    return True


def strip_reading_tail(command):
    """``command`` without trailing chain parts that only read."""
    while True:
        cuts = list(_TAIL_SPLIT_RE.finditer(_masked(command)))
        if not cuts:
            return command
        last = cuts[-1]
        head, tail = command[:last.start()], command[last.end():]
        if not head.strip() or (tail.strip() and not reads(tail)):
            return command
        command = head


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


#: The environment every command runs under, built from scratch: nothing of the
#: machine running the eval reaches a model's command. ``GIT_OPTIONAL_LOCKS=0``
#: keeps ``git status`` from rewriting the index, and ``PYTHONDONTWRITEBYTECODE``
#: keeps ``python3`` from writing bytecode, so a command that only reads leaves
#: the digest as it was.
COMMAND_ENV = {
    "PATH": "/opt/crayon/bin:/usr/local/bin:/usr/bin:/bin",
    "HOME": "/srv/home",
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
    "GIT_OPTIONAL_LOCKS": "0",
    "GIT_PAGER": "cat",
    "PAGER": "cat",
    "PYTHONDONTWRITEBYTECODE": "1",
    "TERM": "dumb",
}

#: How long one command may run, and how much of its output a model sees.
TIMEOUT = 20
LIMIT = 20000


class Repo(object):
    """A real copy of a recorded state, in which every tool call is carried out.

    The copy lives at ``root`` on the machine running the eval; ``runner`` runs
    commands against the same copy where the model's commands run (a workshop
    for a live model, the host for a replay of fixed commands). ``Read`` and
    ``Glob`` read the copy at ``root``; ``Grep`` and ``Bash`` go through the
    runner. ``overrides`` answer a command from the replayed history instead,
    where the history was written rather than recorded (a refusal no real state
    here would print).

    A call is consequential when it would change something: ``serve`` returns
    ``(None, True)`` for it, and the episode ends there.
    """

    def __init__(self, root, runner, overrides=()):
        self.root = os.path.realpath(str(root))
        self.runner = runner
        self.overrides = list(overrides)
        self.before = None

    def start(self):
        """Hand the copy to the runner and take its digest: the state nothing may change."""
        self.runner.reset(os.path.dirname(self.root))
        self.before = self.runner.digest()

    # -- paths ----------------------------------------------------------------

    def _to_disk(self, text):
        return (text or "").replace(WORKDIR, self.root)

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

        A model's argument of the wrong type, or a string holding a NUL byte, is
        answered the way a harness answers it: as a tool error the model sees.
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
        return "\n".join(lines[offset: offset + limit])[:LIMIT]

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
        """``rg`` through the runner: a linear-time search under the command time limit."""
        wrong = self._not_text(args, "pattern", "path", "glob")
        if wrong:
            return wrong
        full = self._inside(args.get("path", ""))
        if full is None:
            return "Error: %s is outside the repository" % args.get("path")
        argv = ["rg", "--no-heading", "--line-number", "--color", "never",
                "--glob", "!.git"]
        if args.get("glob"):
            argv += ["--glob", args["glob"]]
        argv += ["-e", args.get("pattern") or "", "--", self._shown(full)]
        output, code = self.runner.run_argv(argv)
        if code == 1:
            return "(no matches)"
        if code != 0:
            return "Error: %s" % (output.strip() or "the search failed (exit %d)" % code)
        lines = [line[2:] if line.startswith("./") else line for line in output.splitlines()]
        return "\n".join(lines[:200]) or "(no matches)"

    # -- the shell ------------------------------------------------------------

    def bash(self, command):
        """(output, exit) for a command that changed nothing, else None.

        A ``command`` that is not a string, or that holds a NUL byte, is answered
        as a usage error.
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
        if mutating(command):
            return None
        output, code = self.runner.run(command)
        if self.runner.digest() != self.before:
            return None
        return output, code

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


def run_episode(provider, spec, messages, tools, repo, max_turns=6, scope=None):
    """Live turns until the first consequential action (or ``max_turns``).

    Returns a trace: ``turns`` (every live turn), ``decisive`` (what ended the
    episode: ``{"type": "call", "call": ...}``, ``{"type": "text"}`` or
    ``{"type": "none"}`` when the turn cap was reached), ``served`` (the calls
    carried out on the way) and ``retries`` (how many empty turns were re-sent,
    once each).

    Any exception from the provider or a tool leaves as a ``ProviderError`` or a
    ``BudgetExceeded`` carrying the cost of the turns already held (``carry_cost``),
    so the case's record keeps them.
    """
    messages = list(messages)
    turns, served = [], []
    served_ids = []
    retries = 0
    offered = [tool["function"]["name"] for tool in tools or ()]
    for _ in range(max_turns):
        try:
            turn = provider.complete(spec, messages, tools=tools, scope=scope)
            turn, retried = retry_empty_turn(provider, turn, spec, messages, tools=tools,
                                             scope=scope)
        except Exception as exc:
            raise carry_cost(exc, sum(held["usage"]["cost"] for held in turns))
        retries += retried
        turns.append(turn)
        if not turn["tool_calls"]:
            return {"turns": turns, "decisive": {"type": "text"}, "served": served,
                    "served_ids": served_ids, "retries": retries}
        messages.append(assistant_message(turn))
        for call in turn["tool_calls"]:
            if call["name"] not in TOOL_SCHEMAS:
                # A name no tool has is answered the way a harness answers it,
                # and the model goes on; it acted on nothing.
                result = "Error: no tool named %r; the tools are: %s" % (
                    call["name"], ", ".join(offered))
                messages.append({"role": "tool", "tool_call_id": call["id"],
                                 "content": result})
                continue
            try:
                result, consequential = repo.serve(call)
            except Exception as exc:
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
