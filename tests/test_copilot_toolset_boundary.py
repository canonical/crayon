"""V4 security regression guard: the ``READONLY`` / ``DENY`` toolset is unchanged.

Plan 03-02 wires ``PermissionHandler.approve_all`` into the Copilot session so
the non-interactive live path can auto-approve tool calls. That auto-approval is
only safe while the available toolset stays the bounded read-only allowlist
(``grep`` / ``glob`` / ``view``) and the explicit denylist of every write / exec /
network tool. These tests pin both source-qualified ``builtin:<name>`` sets so a
future edit to :mod:`dogen.adapters.copilot.tools` cannot quietly broaden what
``approve_all`` is allowed to approve (V4; RESEARCH Security Domain). ``tools.py``
itself is NOT modified in Phase 3 — this guard locks it.

The assertion shape is copied from
``tests/test_copilot_mapping.py::test_toolsets_are_source_qualified_builtins``.
"""

from copilot import ToolSet

from dogen.adapters.copilot.tools import DENY, READONLY


def test_readonly_set_unchanged() -> None:
    """Pin the read-only allowlist to exactly ``grep`` / ``glob`` / ``view``.

    Asserts ``READONLY`` is a ``ToolSet`` whose source-qualified filter strings
    are precisely the three read-only lookup tools — no broadening.
    """
    assert isinstance(READONLY, ToolSet)
    expected = {"grep", "glob", "view"}
    assert set(READONLY.to_list()) == {f"builtin:{name}" for name in expected}


def test_deny_set_unchanged() -> None:
    """Pin the denylist to its exact eight write / exec / network tool names.

    Asserts ``DENY`` is a ``ToolSet`` whose source-qualified filter strings are
    precisely the confirmed mutating / host-reaching tools — no narrowing that
    would let a denied tool slip through.
    """
    assert isinstance(DENY, ToolSet)
    expected = {
        "bash",
        "edit",
        "create",
        "stop_bash",
        "sql",
        "task",
        "skill",
        "web_fetch",
    }
    assert set(DENY.to_list()) == {f"builtin:{name}" for name in expected}
