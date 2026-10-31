import json

import pytest

from analysis.journal import ToolCall, no_read, parse_calls, read_before_edit, reads_guide
from analysis.result import Status

GUIDE = "rules/interfaces.md"


def entry(when: str | None, *calls: tuple[str, dict[str, object]]) -> str:
    content = [{"type": "text", "text": "thinking"}] + [
        {"type": "toolCall", "name": n, "arguments": a} for n, a in calls
    ]
    line: dict[str, object] = {"type": "message", "message": {"role": "assistant", "content": content}}
    if when:
        line["timestamp"] = when
    return json.dumps(line)


def asked(call_id: str, name: str, args: dict[str, object]) -> str:
    """An assistant message with one call, as omp writes it (with the call's id)."""
    content = [{"type": "toolCall", "id": call_id, "name": name, "arguments": args}]
    return json.dumps({"type": "message", "message": {"role": "assistant", "content": content}})


def answered(call_id: str, *, error: bool) -> str:
    """The call's result, as omp writes it."""
    message = {"role": "toolResult", "toolCallId": call_id, "toolName": "read", "content": [], "isError": error}
    return json.dumps({"type": "message", "message": message})


def call(index: int, name: str, path: str, *, succeeded: bool | None = True) -> ToolCall:
    return ToolCall(index, name, {"path": path}, succeeded)


def test_parse_calls_orders_files_by_time_and_skips_noise() -> None:
    main_file = [
        json.dumps({"type": "session", "timestamp": "2026-10-31T10:00:00Z"}),
        entry("2026-10-31T10:00:01Z", ("read", {"path": "."}), ("bash", {"command": "ls"})),
        "not json at all",
        entry("2026-10-31T10:00:05Z", ("write", {"path": "src/cli.ts"})),
        entry(None, ("edit", {"path": "src/cli.ts"})),  # no timestamp: stays after the write
    ]
    subagent_file = [
        json.dumps({"type": "session", "timestamp": "2026-10-31T10:00:02Z"}),
        entry("2026-10-31T10:00:03Z", ("read", {"path": "rule://interfaces"})),
    ]
    calls = parse_calls([*main_file, *subagent_file])
    assert [(c.index, c.name, c.target()) for c in calls] == [
        (1, "read", "."),
        (2, "bash", "ls"),
        (3, "read", "rule://interfaces"),
        (4, "write", "src/cli.ts"),
        (5, "edit", "src/cli.ts"),
    ]


def test_parse_calls_matches_each_call_with_its_result() -> None:
    lines = [
        asked("a", "read", {"path": "/x/rules/interfaces.md"}),
        answered("a", error=True),
        asked("b", "read", {"path": "rule://interfaces"}),
        answered("b", error=False),
        asked("c", "write", {"path": "src/cli.ts"}),  # no result: the run was killed
        answered("zzz", error=False),  # a result for no known call
    ]
    assert [c.succeeded for c in parse_calls(lines)] == [False, True, None]


def test_parse_calls_tolerates_odd_entries() -> None:
    lines = [
        json.dumps([1, 2]),
        json.dumps({"type": "message", "message": {"content": "plain text"}}),
        json.dumps({"type": "message", "message": {"content": [{"type": "toolCall", "arguments": {}}]}}),
        json.dumps(
            {"type": "message", "timestamp": "garbage", "message": {"content": [{"type": "toolCall", "name": "read"}]}}
        ),
        json.dumps({"type": "message", "message": {"role": "toolResult", "isError": False}}),
    ]
    assert [(c.name, dict(c.arguments), c.succeeded) for c in parse_calls(lines)] == [("read", {}, None)]


@pytest.mark.parametrize(
    ("guide", "path", "reads"),
    [
        (GUIDE, "rule://interfaces", True),
        (GUIDE, "rule://interfaces.md", True),
        (GUIDE, "rule://interfaces:1-40", True),
        (GUIDE, "/tmp/sandbox/.omp/plugins/piebird-workflow-rules/rules/interfaces.md", True),
        (GUIDE, "rules/interfaces.md:raw", True),
        (GUIDE, "rules/interfaces.md", True),
        (GUIDE, "rule://interfaces-extra", False),
        (GUIDE, "rule://commits", False),
        (GUIDE, "skill://failure-classes", False),
        (GUIDE, "/tmp/notrules/interfaces.md", False),
        (GUIDE, "rules/interfaces.md.bak", False),
        ("skills/interfaces/SKILL.md", "skill://interfaces", True),
        ("skills/interfaces/SKILL.md", "skill://interfaces/SKILL.md", True),
        ("skills/interfaces/SKILL.md", "skill://interfaces/references/more.md", False),
        ("skills/interfaces/SKILL.md", "/x/skills/interfaces/SKILL.md", True),
    ],
)
def test_reads_guide(guide: str, path: str, reads: bool) -> None:
    assert reads_guide(call(1, "read", path), guide) is reads


def test_reads_guide_counts_only_the_read_tool() -> None:
    assert not reads_guide(ToolCall(1, "bash", {"command": "cat rules/interfaces.md"}), GUIDE)
    assert not reads_guide(call(1, "write", "rules/interfaces.md"), GUIDE)


def test_read_before_edit() -> None:
    read, write = call(2, "read", "rule://interfaces"), call(3, "write", "src/cli.ts")
    before = read_before_edit([call(1, "read", "."), read, write], GUIDE)
    assert before.status is Status.PASS
    assert "call 2" in before.detail
    assert "src/cli.ts (call 3)" in before.detail
    after = read_before_edit([call(1, "edit", "src/a.ts"), call(2, "read", "rule://interfaces")], GUIDE)
    assert after.status is Status.FAIL
    assert "after the first edit: edit src/a.ts (call 1)" in after.detail
    never = read_before_edit([call(1, "ast_edit", "src/a.ts")], GUIDE)
    assert never.status is Status.FAIL
    assert "never read in 1 calls" in never.detail


def test_read_before_edit_needs_a_read_that_succeeded() -> None:
    wrong_path = call(1, "read", "/x/rules/interfaces.md", succeeded=False)
    edit = call(2, "edit", "src/cli.ts")
    failed = read_before_edit([wrong_path, edit], GUIDE)
    assert failed.status is Status.FAIL
    assert "(unsuccessful reads: read /x/rules/interfaces.md (call 1) errored)" in failed.detail
    unanswered = read_before_edit([call(1, "read", "rule://interfaces", succeeded=None)], GUIDE)
    assert unanswered.status is Status.FAIL
    assert "had no result" in unanswered.detail
    retried = read_before_edit([wrong_path, call(2, "read", "rule://interfaces"), call(3, "edit", "src/a.ts")], GUIDE)
    assert retried.status is Status.PASS
    assert retried.detail.startswith("read rule://interfaces (call 2)")
    late = read_before_edit([wrong_path, edit, call(3, "read", "rule://interfaces")], GUIDE)
    assert late.status is Status.FAIL
    assert "(call 3) came after the first edit" in late.detail


def test_read_before_edit_without_edits_or_calls() -> None:
    assert read_before_edit([call(1, "read", "rule://interfaces")], GUIDE).status is Status.PASS
    assert read_before_edit([call(1, "bash", "x")], GUIDE).status is Status.FAIL
    assert read_before_edit([], GUIDE).status is Status.UNMEASURED
    assert read_before_edit(None, GUIDE).status is Status.UNMEASURED


def test_no_read() -> None:
    assert no_read([call(1, "read", "src/cart.ts"), call(2, "edit", "src/cart.ts")], GUIDE).status is Status.PASS
    read = no_read([call(1, "edit", "src/cart.ts"), call(2, "read", "rule://interfaces")], GUIDE)
    assert read.status is Status.FAIL
    assert "call 2" in read.detail
    assert no_read([], GUIDE).status is Status.UNMEASURED


def test_no_read_ignores_reads_that_failed() -> None:
    attempt = no_read([call(1, "read", "rules/interfaces.md", succeeded=False), call(2, "edit", "src/cart.ts")], GUIDE)
    assert attempt.status is Status.PASS
    assert "(unsuccessful reads: read rules/interfaces.md (call 1) errored)" in attempt.detail


def test_describe_names_the_file_of_an_edit_patch() -> None:
    edit = ToolCall(4, "edit", {"i": "Clamp totals", "input": "[src/cart.ts#164A]\nPUT 10.=18:\n+x"})
    assert edit.describe() == "edit src/cart.ts (call 4)"
    assert ToolCall(5, "bash", {"command": "ls"}).describe() == "bash ls (call 5)"
    assert ToolCall(6, "todo", {}).describe() == "todo (call 6)"
