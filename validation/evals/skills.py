"""How the five skills reach a model, the same way for every model.

Dev-time evaluation material. The eval is harness-neutral on purpose: no
harness's own prompt, tool names or loading convention sits between the skill
text and the model. What stands in for a harness is the agentskills.io
progressive-disclosure shape, and nothing more:

- the *catalog* — each skill's frontmatter ``name`` and ``description`` and
  where its ``SKILL.md`` is installed — is always in the system prompt;
- invoking a skill (``/crayon-plan <args>``, the form the skills are documented
  under everywhere) appends that skill's ``SKILL.md`` body to the turn;
- ``references/*.md`` stay on disk, for the model to read when the body says to.

The frontmatter parser is ``scripts/skill_lint.py``'s, imported rather than
copied: one definition site, so the eval and the lint can never disagree about
what a skill declares.
"""

import hashlib
import importlib.util
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SKILLS_ROOT = REPO / "skills"
#: Where ``install.sh`` puts the skills in project mode, relative to the repo the
#: agent works in. The catalog names this path; it names no harness.
INSTALLED_AT = ".agents/skills"


def _load_skill_lint():
    spec = importlib.util.spec_from_file_location(
        "crayon_skill_lint", str(REPO / "scripts" / "skill_lint.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_lint = _load_skill_lint()


class Skill(object):
    def __init__(self, directory):
        self.directory = Path(directory)
        text = (self.directory / "SKILL.md").read_text(encoding="utf-8")
        self.frontmatter, self.body = _lint.split_front_matter(text)
        self.name = self.frontmatter["name"]
        self.description = self.frontmatter["description"]
        self.tools = _lint._tools(self.frontmatter)

    @property
    def location(self):
        return "%s/%s/SKILL.md" % (INSTALLED_AT, self.name)


def load_skills(root=SKILLS_ROOT):
    skills = [Skill(path) for path in sorted(Path(root).glob("crayon-*")) if path.is_dir()]
    if not skills:
        raise RuntimeError("no skills found under %s" % root)
    return {skill.name: skill for skill in skills}


def bundle_sha256(root=SKILLS_ROOT):
    """One digest over every file a model could be shown: provenance for a run."""
    digest = hashlib.sha256()
    for path in sorted(Path(root).glob("crayon-*/**/*.md")):
        digest.update(str(path.relative_to(root)).encode("utf-8") + b"\0")
        digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest()


def catalog(skills):
    """The always-present skill listing, in the agentskills.io shape."""
    lines = ["<available_skills>"]
    for skill in skills.values():
        lines.extend(
            [
                "<skill>",
                "<name>%s</name>" % skill.name,
                "<description>%s</description>" % skill.description,
                "<location>%s</location>" % skill.location,
                "</skill>",
            ]
        )
    lines.append("</available_skills>")
    return "\n".join(lines)


SELECTION_PROMPT = """You are an AI agent working in a software repository. The \
following Agent Skills are installed:

{catalog}

Decide which ONE installed skill should handle the user's request below. Answer \
with the skill's name only, exactly as listed (for example: crayon-plan). If no \
installed skill applies, answer: none"""


def selection_system_prompt(skills):
    return SELECTION_PROMPT.format(catalog=catalog(skills))


AGENT_PROMPT = """You are an AI agent working in the software repository at \
{cwd}. You act through the tools you are given; every path is relative to that \
repository unless it is absolute. The user is a Technical Author. When you need \
something from them, ask; when you are done or must stop, say so plainly and end \
your turn.

The following Agent Skills are installed. When the user invokes one as \
/<name>, its instructions are appended to their message; follow them. Read a \
skill's reference files from its location when its instructions tell you to.

{catalog}"""


def agent_system_prompt(skills, cwd):
    return AGENT_PROMPT.format(cwd=cwd, catalog=catalog(skills))


_INVOKE_RE = re.compile(r"^/(crayon-[a-z]+)\b[ \t]*(.*)$", re.DOTALL)


def expand_invocation(message, skills):
    """``/crayon-plan args`` -> (skill name, the user turn with the body appended).

    A message that invokes no installed skill is returned unchanged with a name
    of None.
    """
    match = _INVOKE_RE.match(message.strip())
    if not match or match.group(1) not in skills:
        return None, message
    skill = skills[match.group(1)]
    args = match.group(2).strip()
    expanded = (
        "/%s %s\n\n<skill_instructions name=\"%s\" location=\"%s\">\n%s\n"
        "</skill_instructions>" % (skill.name, args, skill.name, skill.location,
                                   skill.body.strip())
    )
    return skill.name, expanded
