import copy
import fcntl
import json
import os
import re
import time
from contextlib import contextmanager
from pathlib import Path

import yaml

from iot_core.setup.keys import KEYS, ROOT, read_values

BACKUP_KEEP = 50
KEY_RE = re.compile(r"""^(\s*)(["']?)([^"'#:\s][^"'#:]*)\2:(?=\s|$)(.*)$""")


class EditError(Exception):
    pass


class Conflict(EditError):
    pass


def _indent(line):

    return len(line) - len(line.lstrip(" "))


def _meaningful(line):

    text = line.strip()
    return bool(text) and not text.startswith("#")


def _find_child(lines, start, end, part):

    child = None

    for n in range(start, end):
        if not _meaningful(lines[n]):
            continue
        ind = _indent(lines[n])
        if child is None:
            child = ind
        if ind < child:
            break
        if ind != child:
            continue
        m = KEY_RE.match(lines[n])
        if m and m.group(3).strip() == part:
            return n

    raise EditError("key " + part + " was not found in the file")


def _block_end(lines, n):

    base = _indent(lines[n])

    for m in range(n + 1, len(lines)):
        if _meaningful(lines[m]) and _indent(lines[m]) <= base and not lines[m].lstrip().startswith("- "):
            return m

    return len(lines)


def render(value):

    if isinstance(value, bool):
        return "true" if value else "false"

    if isinstance(value, float):
        return repr(value)

    if isinstance(value, str) and value != "na":
        return json.dumps(value, ensure_ascii=False)

    return str(value)


def _split_comment(rest):

    m = re.match(r"^(\s*)(.*?)(\s+#.*)?$", rest)
    return m.group(1) or " ", m.group(2), m.group(3) or ""


def _set_flow(line, part, value):

    pattern = re.compile(r"([{,]\s*)(" + re.escape(part) + r")(\s*:\s*)([^,}]+?)(\s*)(?=[,}])")
    new, count = pattern.subn(lambda m: m.group(1) + m.group(2) + m.group(3) + render(value) + m.group(5), line, count=1)

    if count != 1:
        raise EditError("key " + part + " was not found on the line")

    return new


def _set_list(lines, n, value):

    end = _block_end(lines, n)
    items = [m for m in range(n + 1, end) if lines[m].lstrip().startswith("- ")]

    if not items:
        raise EditError("the list is empty or is not a block")

    pad = " " * _indent(lines[items[0]])
    new_items = [f"{pad}- {entry}\n" for entry in value]
    return lines[:items[0]] + new_items + lines[items[-1] + 1:]


def set_value(text, path, value):

    lines = text.splitlines(keepends=True)
    start, end = 0, len(lines)

    for i, part in enumerate(path):
        n = _find_child(lines, start, end, part)
        match = KEY_RE.match(lines[n])
        rest = match.group(4)
        last = i == len(path) - 1

        if not last and rest.strip().startswith("{"):
            if i != len(path) - 2:
                raise EditError("a nested inline map is not supported")
            lines[n] = _set_flow(lines[n], path[-1], value)
            return "".join(lines)

        if last:
            if isinstance(value, list):
                lines = _set_list(lines, n, value)
                return "".join(lines)
            space, old, comment = _split_comment(rest)
            if not old or old.startswith(("{", "[", "|", ">")):
                raise EditError("key " + part + " has no plain value")
            newline = "\n" if lines[n].endswith("\n") else ""
            lines[n] = lines[n][: match.start(4)] + space + render(value) + comment + newline
            return "".join(lines)

        start, end = n + 1, _block_end(lines, n)

    raise EditError("empty path")


def _assign(tree, path, value):

    for part in path[:-1]:
        tree = tree[part]
    tree[path[-1]] = value


def edit_text(text, path, value):

    """Nový text súboru. Overí, že sa zmenil presne jeden kľúč."""

    new = set_value(text, path, value)
    expected = copy.deepcopy(yaml.safe_load(text))
    _assign(expected, path, value)

    if yaml.safe_load(new) != expected:
        raise EditError("the edit would change other values, write cancelled")

    return new


@contextmanager
def _lock(var_dir):

    var_dir.mkdir(parents=True, exist_ok=True)

    with open(var_dir / "setup.lock", "w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _write_atomic(path, text):

    tmp = path.with_name(path.name + ".setup-tmp")
    mode = path.stat().st_mode & 0o777

    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())

    os.chmod(tmp, mode)
    os.replace(tmp, path)


def _backup(var_dir, path, text, stamp):

    folder = var_dir / "setup-backup"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{stamp}_{path.name}").write_text(text, encoding="utf-8")

    for old in sorted(folder.iterdir())[:-BACKUP_KEEP]:
        old.unlink()


def apply(changes, request_text="", confirmed=False, root=ROOT, var_dir=None):

    """changes: [{"key", "old", "new"}]. Zapíše všetko, alebo nič."""

    root = Path(root)
    var_dir = Path(var_dir) if var_dir else root / "var"

    with _lock(var_dir):
        current = read_values(root)

        for change in changes:
            if current[change["key"]] != change["old"]:
                raise Conflict("The file changed in the meantime. Repeat the proposal.")

        texts = {}

        for change in changes:
            item = KEYS[change["key"]]
            path = root / item.file
            if item.file not in texts:
                texts[item.file] = (path.read_text(encoding="utf-8"),) * 2
            original, edited = texts[item.file]
            texts[item.file] = (original, edit_text(edited, item.path, change["new"]))

        stamp = time.strftime("%Y%m%d-%H%M%S")

        for file, (original, edited) in texts.items():
            _backup(var_dir, root / file, original, stamp)

        for file, (original, edited) in texts.items():
            _write_atomic(root / file, edited)

        entry = {
            "ts": time.time(),
            "request": request_text,
            "confirmed": bool(confirmed),
            "changes": [{"key": c["key"], "old": c["old"], "new": c["new"]} for c in changes],
            "restart": any(KEYS[c["key"]].restart for c in changes),
        }

        with open(var_dir / "setup-changes.jsonl", "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return entry


def history(limit=20, root=ROOT, var_dir=None):

    var_dir = Path(var_dir) if var_dir else Path(root) / "var"
    path = var_dir / "setup-changes.jsonl"

    if not path.exists():
        return []

    entries = []

    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            entries.append(json.loads(line))
        except ValueError:
            continue

    return entries[-limit:][::-1]
