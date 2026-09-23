"""The neutral agent surface: seven tools, a replayed history, a decisive action.

Dev-time evaluation material. Every model sees the same tools, and the tools
carry the names the skills declare in their ``allowed-tools`` frontmatter
(``Read``, ``Bash``, ``Glob``, ``Grep``, ``Write``, ``Edit``,
``AskUserQuestion``), with plain JSON-schema parameters. A model is offered only
the tools its invoked skill declares.

Lane B uses ``run_episode``: the conversation up to a recorded ``dogen`` output
is replayed as real tool calls and results, then the model acts. Looking is
free: reads, searches, the inspection commands and the read-only ``dogen``
calls the case recorded are answered from a ``VirtualRepo`` and the episode
goes on. The first *consequential* action ends it — a ``dogen`` verb that
writes, any other command, a write, a question to the author, or a turn with
no tool call — and that action is what the case grades.
"""

import fnmatch
import json
import re
import shlex

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

#: The answer to a read-only ``dogen`` call the case did not record. Looking is
#: never graded, so it must not end the episode; it must not invent output
#: either.
NOT_RECORDED = ("(this session replays a recorded state; the output of this "
                "read-only command was not recorded — act on the outputs above)")

#: ``dogen`` verbs that only look. Anything else a model runs is consequential.
_READONLY_DOGEN_RE = re.compile(
    r"^dogen\s+(version|show|summary|verify|context\s+show|resume\s+\S+\s+--dry-run"
    r"|[a-z-]+(\s+[a-z-]+)?\s+--help)\b"
)
#: Shell inspection a careful agent does before acting; answered, never graded.
_INSPECT_RE = re.compile(r"^(cat|ls|head|tail|sed\s+-n|grep|find|wc|pwd|echo|"
                         r"git\s+(status|log|diff|show))\b")


#: Setup is not the graded action: naming variables, creating a directory under
#: the staging tree (or one named by a variable), and waiting. A command made
#: only of such parts, joined by ``;``/``&&`` or newlines, is answered.
_SETUP_PART_RE = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_]*=\S*|"
    r"mkdir\s+-p\s+((/srv/toyq/)?\.dogen/staging/\S+|\$\{?[A-Za-z_]\S*)|"
    r"sleep\s+\d+(\.\d+)?)$"
)


def _is_setup(command):
    parts = [part.strip() for part in re.split(r"&&|;|\n", command) if part.strip()]
    return bool(parts) and all(_SETUP_PART_RE.match(part) for part in parts)


def normalise(command):
    """A command as typed, minus what does not change its meaning here.

    Quotes are dropped, whitespace collapsed, and a trailing ``2>&1`` removed,
    so ``dogen show "cfg" --json 2>&1`` answers like ``dogen show cfg --json``.
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


class VirtualRepo(object):
    """A read-only file tree plus the recorded answers to read-only commands."""

    def __init__(self, files, replies):
        self.files = dict(files)
        self.replies = list(replies)

    @staticmethod
    def _rel(path):
        path = (path or "").strip()
        if path.startswith(WORKDIR):
            path = path[len(WORKDIR):]
        path = path.lstrip("/")
        while path.startswith("./"):
            path = path[2:]
        return path

    def read(self, args):
        path = self._rel(args.get("file_path", ""))
        if path not in self.files:
            return "Error: file not found: %s" % path
        lines = self.files[path].split("\n")
        offset = max(int(args.get("offset") or 1), 1) - 1
        limit = int(args.get("limit") or len(lines))
        return "\n".join(lines[offset: offset + limit])

    def glob(self, args):
        base = self._rel(args.get("path", "")).rstrip("/")
        pattern = args.get("pattern", "*")
        if base:
            pattern = base + "/" + pattern
        hits = [p for p in sorted(self.files)
                if fnmatch.fnmatch(p, pattern) or fnmatch.fnmatch(p, pattern.replace("**/", ""))]
        return "\n".join(hits) or "(no matches)"

    def grep(self, args):
        try:
            pattern = re.compile(args.get("pattern", ""))
        except re.error as exc:
            return "Error: bad pattern: %s" % exc
        base = self._rel(args.get("path", "")).rstrip("/")
        out = []
        for path in sorted(self.files):
            if base and not (path == base or path.startswith(base + "/")):
                continue
            if args.get("glob") and not fnmatch.fnmatch(path.split("/")[-1], args["glob"]):
                continue
            for number, line in enumerate(self.files[path].split("\n"), 1):
                if pattern.search(line):
                    out.append("%s:%d:%s" % (path, number, line))
        return "\n".join(out[:200]) or "(no matches)"

    def bash(self, command):
        """(output, exit) for a command this repo can answer, else None.

        A reply matches on the normalised command (``normalise``), either
        exactly (``exact``) or by regex (``re``). Recorded read-only answers
        come first; then an unrecorded read-only ``dogen`` call, a shell
        inspection, or creating a directory under ``.dogen/staging/`` is
        answered without ending the episode.
        """
        raw, command = command, normalise(command)
        for reply in self.replies:
            if ("exact" in reply and command == reply["exact"]) or \
                    ("re" in reply and re.search(reply["re"], command)):
                return reply["output"], reply["exit"]
        if _READONLY_DOGEN_RE.match(command):
            return NOT_RECORDED, 0
        if _is_setup(raw.strip()):
            return "", 0
        if _INSPECT_RE.match(command) and not re.search(r"[;&|>]", command):
            return self._inspect(command), 0
        return None

    def _inspect(self, command):
        try:
            words = shlex.split(command)
        except ValueError:
            words = command.split()
        paths = [self._rel(w) for w in words[1:] if not w.startswith("-")]
        if words[0] == "cat":
            return "\n".join(self.files.get(p, "cat: %s: No such file" % p) for p in paths)
        if words[0] in ("ls", "find"):
            base = paths[0].rstrip("/") if paths else ""
            return "\n".join(p for p in sorted(self.files)
                             if not base or p.startswith(base + "/")) or "(empty)"
        if words[0] == "pwd":
            return WORKDIR
        return "(no output)"

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


def history_messages(steps):
    """Resolved steps -> the assistant/tool/user messages that replay them.

    A step is ``{"user": text}``, ``{"assistant": text}``, a shell step
    ``{"cmd", "exit", "output"}``, or any other tool call
    ``{"call": {"name", "arguments"}, "result": text}``.
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
        call_id = "h%d" % index
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
    ``{"type": "none"}`` when the turn cap was reached) and ``served`` (the
    looking the model did on the way).
    """
    messages = list(messages)
    turns, served = [], []
    for _ in range(max_turns):
        turn = provider.complete(spec, messages, tools=tools, cache=cache, scope=scope)
        turns.append(turn)
        if not turn["tool_calls"]:
            return {"turns": turns, "decisive": {"type": "text"}, "served": served}
        messages.append(assistant_message(turn))
        for call in turn["tool_calls"]:
            result, consequential = repo.serve(call)
            if consequential:
                return {"turns": turns, "decisive": {"type": "call", "call": call},
                        "served": served}
            served.append({"name": call["name"], "arguments": call["arguments"]})
            messages.append({"role": "tool", "tool_call_id": call["id"],
                             "content": result})
    return {"turns": turns, "decisive": {"type": "none"}, "served": served}
