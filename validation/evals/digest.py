#!/usr/bin/env python3
"""One digest over a sandbox's files and git index: did a command change anything?

Dev-time evaluation material. ``tree(root)`` hashes every regular file and
symlink under ``root`` (its path, permission bits and bytes, or its link
target), plus, for each git repository found, the index as ``git ls-files
--stage`` lists it. Directories are not hashed, so creating an empty one, such
as a staging directory, changes nothing; ``.git/index`` itself is not hashed
either, since a read refreshes its timestamps, and its staged content is
hashed instead. ``home`` beside the repository is left out: it is the command's
throwaway ``HOME``, not the repository.

The same file runs on the host (imported) and inside a workshop (as a script),
so both runners decide alike::

    python3 digest.py /srv
"""

import hashlib
import os
import subprocess
import sys

SKIPPED = ("home",)


def tree(root):
    digest = hashlib.sha256()
    root = os.path.realpath(root)
    for directory, dirs, files in os.walk(root):
        rel_dir = os.path.relpath(directory, root)
        if rel_dir == ".":
            dirs[:] = sorted(d for d in dirs if d not in SKIPPED)
        else:
            dirs[:] = sorted(dirs)
        if os.path.basename(directory) == ".git":
            files = [name for name in files if name != "index"]
            listing = subprocess.run(
                ["git", "--git-dir", directory, "ls-files", "--stage", "-z"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                     "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null",
                     "GIT_OPTIONAL_LOCKS": "0"},
            ).stdout
            digest.update(b"index\0" + rel_dir.encode("utf-8", "surrogateescape") + b"\0"
                          + listing + b"\0")
        for name in sorted(files):
            full = os.path.join(directory, name)
            rel = os.path.relpath(full, root).encode("utf-8", "surrogateescape")
            if os.path.islink(full):
                digest.update(b"link\0" + rel + b"\0"
                              + os.readlink(full).encode("utf-8", "surrogateescape") + b"\0")
                continue
            if not os.path.isfile(full):
                continue
            mode = os.stat(full).st_mode & 0o777
            digest.update(b"file\0" + rel + b"\0" + str(mode).encode() + b"\0")
            with open(full, "rb") as handle:
                for block in iter(lambda: handle.read(1 << 20), b""):
                    digest.update(block)
            digest.update(b"\0")
    return digest.hexdigest()


if __name__ == "__main__":
    print(tree(sys.argv[1] if len(sys.argv) > 1 else "."))
