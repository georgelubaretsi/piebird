"""An omp journal's tool calls, and whether the agent read the suite's guide (pure).

A journal is every session file of the run concatenated in path order, so a subagent's file
comes after its parent's whatever the time: calls are put in time order by their entry's
timestamp (calls without one keep their place after the previous call). Each call is matched
with its result (a `toolResult` message with the call's `toolCallId` and `isError`).

The guide counts as read only through the `read` tool, and only when that call's result
succeeded: a read that errored (a wrong path) or has no result (the run was killed) doesn't
count. Reading it through `bash` does not count either (not seen in past runs).
"""

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import PurePosixPath

from analysis.result import Result, failed, passed, unmeasured

EDITS = frozenset({"write", "edit", "ast_edit"})
READ = "read"
# omp's read tool takes selectors after the path (`file.md:10-20`, `file.md:raw`).
SELECTOR = re.compile(r":(?:raw|conflicts|img|-?\d[\d,+\-:]*)(?::raw)?$")
EPOCH = datetime.min.replace(tzinfo=UTC)
# omp's edit tool names its files in its patch: `[src/cart.ts#164A]`.
PATCH_FILE = re.compile(r"^\[([^\]#\n]+)#[0-9A-Fa-f]+\]", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class ToolCall:
    index: int  # 1-based position in time order
    name: str
    arguments: Mapping[str, object]
    succeeded: bool | None = None  # its result's outcome; None: no result in the journal

    def target(self) -> str:
        """The call's path (an edit patch's first file, else the first string argument), for details."""
        path = self.arguments.get("path")
        if isinstance(path, str):
            return path
        patch = self.arguments.get("input")
        named = PATCH_FILE.search(patch) if isinstance(patch, str) else None
        if named:
            return named.group(1)
        return next((v for v in self.arguments.values() if isinstance(v, str)), "")

    def describe(self) -> str:
        target = self.target()
        if not target:
            return f"{self.name} (call {self.index})"
        shown = target if len(target) <= 80 else target[:79] + "…"
        return f"{self.name} {shown} (call {self.index})"


@dataclass(frozen=True, slots=True)
class _Found:
    when: datetime
    order: int
    call_id: str | None
    name: str
    arguments: Mapping[str, object]


def parse_calls(lines: Iterable[str]) -> list[ToolCall]:
    """Tool calls in time order, each with its result's outcome; lines that aren't JSON entries
    are skipped."""
    found: list[_Found] = []
    outcomes: dict[str, bool] = {}
    when = EPOCH
    for line in lines:
        entry = _json_object(line)
        if entry is None:
            continue
        when = _timestamp(entry.get("timestamp")) or when
        found.extend(_Found(when, len(found), cid, name, args) for cid, name, args in _calls_in(entry))
        outcome = _outcome(entry)
        if outcome is not None:
            outcomes[outcome[0]] = outcome[1]
    found.sort(key=lambda f: (f.when, f.order))
    return [
        ToolCall(i, f.name, f.arguments, outcomes.get(f.call_id) if f.call_id else None)
        for i, f in enumerate(found, start=1)
    ]


def guide_names(guide: str) -> frozenset[str]:
    """Names an internal URL can give the guide: `rules/x.md` → x; `skills/x/SKILL.md` → x."""
    path = PurePosixPath(guide)
    names = {path.stem}
    if path.name == "SKILL.md" and path.parent.name:
        names.add(path.parent.name)
    return frozenset(names)


def reads_guide(call: ToolCall, guide: str) -> bool:
    """Whether the call tries to read the guide, whatever its outcome."""
    if call.name != READ:
        return False
    target = SELECTOR.sub("", call.target().strip())
    match = re.fullmatch(r"(?:rule|skill)://([^/:]+?)(?:\.md|/SKILL\.md)?/?", target)
    if match:
        return match.group(1) in guide_names(guide)
    clean = guide.strip("/")
    return target == clean or target.endswith("/" + clean)


def read_before_edit(calls: Sequence[ToolCall] | None, guide: str) -> Result:
    if calls is None:
        return unmeasured("no journal.jsonl in the run folder")
    if not calls:
        return unmeasured("the journal has no tool calls")
    read, attempts = _guide_read(calls, guide)
    edit = next((c for c in calls if c.name in EDITS), None)
    first_edit = f"first edit: {edit.describe()}" if edit else "no write/edit/ast_edit call"
    if read is None:
        return failed(f"{guide} never read in {len(calls)} calls{attempts}; {first_edit}")
    if edit is not None and edit.index < read.index:
        return failed(f"{read.describe()} came after the {first_edit}")
    return passed(f"{read.describe()}; {first_edit}")


def no_read(calls: Sequence[ToolCall] | None, guide: str) -> Result:
    if calls is None:
        return unmeasured("no journal.jsonl in the run folder")
    if not calls:
        return unmeasured("the journal has no tool calls")
    read, attempts = _guide_read(calls, guide)
    if read is not None:
        return failed(f"{read.describe()}, of {len(calls)} calls")
    return passed(f"{guide} not read in {len(calls)} calls{attempts}")


def _guide_read(calls: Sequence[ToolCall], guide: str) -> tuple[ToolCall | None, str]:
    """The first read of the guide that succeeded, and a note on the reads before it that didn't."""
    tries = [c for c in calls if reads_guide(c, guide)]
    read = next((c for c in tries if c.succeeded is True), None)
    unread = [c for c in tries if read is None or c.index < read.index]
    if not unread:
        return read, ""
    shown = ", ".join(f"{c.describe()} {'errored' if c.succeeded is False else 'had no result'}" for c in unread[:3])
    return read, f" (unsuccessful reads: {shown})"


def _json_object(line: str) -> dict[str, object] | None:
    try:
        value: object = json.loads(line)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _calls_in(entry: Mapping[str, object]) -> list[tuple[str | None, str, Mapping[str, object]]]:
    message = entry.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, list):
        return []
    calls: list[tuple[str | None, str, Mapping[str, object]]] = []
    for item in content:
        if not isinstance(item, dict) or item.get("type") != "toolCall":
            continue
        call_id, name, args = item.get("id"), item.get("name"), item.get("arguments")
        if isinstance(name, str):
            calls.append((call_id if isinstance(call_id, str) else None, name, args if isinstance(args, dict) else {}))
    return calls


def _outcome(entry: Mapping[str, object]) -> tuple[str, bool] | None:
    """(call id, succeeded) of a `toolResult` message."""
    message = entry.get("message")
    if not isinstance(message, dict) or message.get("role") != "toolResult":
        return None
    call_id = message.get("toolCallId")
    return (call_id, message.get("isError") is not True) if isinstance(call_id, str) else None
