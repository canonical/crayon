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
_INSPECT_RE = re.compile(
    r"^(cat|ls|head|tail|sed|grep|egrep|find|wc|pwd|echo|printf|cd|tree|file|stat|ps|"
    r"pdfinfo|pdftotext|"
    r"sort|uniq|cut|tr|true|test|\[|which|type|command\s+-v|sha256sum|md5sum|du|diff|"
    r"basename|dirname|realpath|readlink|nl|jq|column|od|xxd|hexdump|strings|cmp|comm|"
    r"fold|fmt|rev|printenv|env|id|whoami|uname|date|"
    r"(python3?\s+-m\s+)?pip3?\s+(show|list|freeze|index|--version)|python3?\s+(--version|-V)|"
    r"git(\s+(-C\s+\S+|--no-pager))*\s+(status|log|diff|show|ls-files|ls-tree|rev-parse|branch|"
    r"blame|check-ignore|reflog(?!\s+(expire|delete)\b)))(?=\s|$)"
)
#: ``xargs`` and its options: what it runs is checked as the part's command.
_XARGS_RE = re.compile(
    r"^xargs((\s+-[0rtx]+)|(\s+(-[nLPsdIE]|--max-args|--delimiter)(=|\s*)\S+))*(\s+|$)")
#: ``awk`` reads unless its program spawns, redirects, pipes or edits in place;
#: a ``>`` is read as a redirect even where it compares, so doubt stays acting.
_AWK_RE = re.compile(r"^g?awk\s")
_AWK_ACTS_RE = re.compile(r"system|getline|fflush|close\s*\(|[>|]|inplace|--in-place|(^|\s)-f\b")
#: Shell control flow around the commands of a chain. Its keywords are peeled
#: off a part before the part's command word is checked, so a ``for`` loop of
#: ``cat`` calls is looking and a ``for`` loop of ``rm`` calls is not.
_CONTROL_LEAD_RE = re.compile(r"^(do|then|else|elif|if|while|until|!|\{|\()\s+")
_CONTROL_WHOLE_RE = re.compile(
    r"^(done|fi|esac|;;|\}|\)|for\s+\w+\s+in\b.*|case\s+\S+\s+in(\s+[^\s()]+\))?)$")
_CASE_PATTERN_RE = re.compile(r"^[^\s()]+\)\s*")
#: Arguments that turn a reading command into a writing or executing one.
_ACTING_WORD_RE = re.compile(
    r"(^|\s)(-delete|-exec|-execdir|-ok|-okdir|-fprint\S*|-fls|--output\S*)(\s|$)"
    r"|^(sort|tree)\b.*\s-o\b"
    r"|^sed\b.*(\s-i\S*|--in-place|[/;\s]w\s|[/;\s]W\s|/e\b|;\s*e\b)"
    # pdftotext writes a .txt beside its input unless the output is `-` (stdout).
    r"|^pdftotext\b(?!.*\s-\s*$)"
)
#: ``ps`` is on the list above only because a live episode always runs inside
#: the jail (:class:`Jail`), whose own process namespace holds nothing but the
#: command itself: outside it, ``ps`` would show a model the host's processes.
#: Redirections that change nothing on disk; any other ``>`` writes a file.
_HARMLESS_REDIRECT_RE = re.compile(r"\d?>\s*/dev/null|\d?>&\d|&>\s*/dev/null")
_SEGMENT_SPLIT_RE = re.compile(r"\s*(?:&&|\|\||;|\||\n)\s*")
_QUOTED_RE = re.compile(r"'[^']*'|\"(?:\\.|[^\"\\])*\"")

#: Setup is not the graded action: naming variables, creating a directory under
#: the staging tree (or one named by a variable), and waiting.
_SETUP_PART_RE = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_]*=\S*|"
    r"mkdir\s+-p\s+((/srv/toyq/)?\.crayon/staging/\S+|\$\{?[A-Za-z_]\S*)|"
    r"sleep\s+\d+(\.\d+)?)$"
)


_SUBSTITUTION_RE = re.compile(r"\$\(([^()]*)\)|`([^`]*)`")


def _live(command):
    """``command`` with what the shell reads literally masked, length kept.

    A single-quoted span and a backslash-escaped character are literal, so a
    backtick or ``$(`` there runs nothing; inside double quotes both still run.
    """
    out, state, index = [], "", 0
    while index < len(command):
        char = command[index]
        if state == "'":
            out.append("'" if char == "'" else "Q")
            state = "" if char == "'" else state
        elif char == "\\" and index + 1 < len(command):
            out.append("QQ")
            index += 1
        elif char == "'" and state == "":
            out.append(char)
            state = "'"
        elif char == '"':
            out.append(char)
            state = "" if state == '"' else '"'
        else:
            out.append(char)
        index += 1
    return "".join(out)


def _unsubstitute(command):
    """``command`` with each command substitution replaced by a word, or None.

    A substitution is allowed only when what it runs is itself looking, checked
    innermost first; anything else makes the whole command acting. Only a live
    substitution counts: one inside single quotes or escaped is literal text.
    """
    while True:
        match = _SUBSTITUTION_RE.search(_live(command))
        if match is None:
            return command
        group = 1 if match.group(1) is not None else 2
        if not looking(command[match.start(group):match.end(group)]):
            return None
        command = command[:match.start()] + "SUBST" + command[match.end():]


def _segments(command):
    """The parts of a chain, split outside quotes, with harmless redirects dropped.

    None when the command runs an acting substitution or redirects into a file:
    such a command is never "only looking", whatever its parts are.
    """
    command = _unsubstitute(command)
    if command is None or "$(" in _live(command) or "`" in _live(command):
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
#: print(inspect.getsource(subprocess.call))`` looks, and any other use of a
#: name below still acts.
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
)

_TAIL_SPLIT_RE = re.compile(r"\s*(?:&&|\|\||;|\n)\s*")


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
        if _ACTING_WORD_RE.search(part):
            return False
        part = _command_word_first(part)
        if not part:
            continue
        if python and _PYTHON_PART_RE.match(part):
            if _PYTHON_ACTS_RE.search(_PYTHON_READS_RE.sub("READ", part)):
                return False
            continue
        xargs = _XARGS_RE.match(part)
        if xargs:
            part = part[xargs.end():]
            if not part:
                continue
        if _AWK_RE.match(part):
            if _AWK_ACTS_RE.search(part.split(None, 1)[1]):
                return False
            continue
        if not (_INSPECT_RE.match(part) or _READONLY_CRAYON_RE.match(normalise(part))
                or _SETUP_PART_RE.match(part)):
            return False
    return True


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

    def read(self, args):
        full = self._inside(args.get("file_path", ""))
        if full is None:
            return "Error: %s is outside the repository" % args.get("file_path")
        if not os.path.isfile(full):
            return "Error: file not found: %s" % args.get("file_path")
        with open(full, encoding="utf-8", errors="replace") as handle:
            lines = handle.read().split("\n")
        offset = max(int(args.get("offset") or 1), 1) - 1
        limit = int(args.get("limit") or len(lines))
        return "\n".join(lines[offset: offset + limit])[: self.limit]

    def _files(self, base):
        for directory, dirs, files in os.walk(base):
            dirs[:] = sorted(d for d in dirs if d != ".git")
            for name in sorted(files):
                yield os.path.join(directory, name)

    def glob(self, args):
        base = self._inside(args.get("path", "")) or self.root
        pattern = args.get("pattern", "*")
        hits = []
        for full in self._files(base):
            rel = os.path.relpath(full, base)
            if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(rel, pattern.replace("**/", "")):
                hits.append(self._shown(full))
        return "\n".join(hits[:500]) or "(no matches)"

    def grep(self, args):
        try:
            pattern = re.compile(args.get("pattern", ""))
        except re.error as exc:
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
        """(output, exit) for a command carried out or answered here, else None."""
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
    ``{"type": "none"}`` when the turn cap was reached) and ``served`` (the
    looking the model did on the way).
    """
    messages = list(messages)
    turns, served = [], []
    served_ids = []
    offered = [tool["function"]["name"] for tool in tools or ()]
    for _ in range(max_turns):
        turn = provider.complete(spec, messages, tools=tools, cache=cache, scope=scope)
        turns.append(turn)
        if not turn["tool_calls"]:
            return {"turns": turns, "decisive": {"type": "text"}, "served": served,
                    "served_ids": served_ids}
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
            result, consequential = repo.serve(call)
            if consequential:
                return {"turns": turns, "decisive": {"type": "call", "call": call},
                        "served": served, "served_ids": served_ids}
            served.append({"name": call["name"], "arguments": call["arguments"]})
            served_ids.append(call["id"])
            messages.append({"role": "tool", "tool_call_id": call["id"],
                             "content": result})
    return {"turns": turns, "decisive": {"type": "none"}, "served": served,
            "served_ids": served_ids}
