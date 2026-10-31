import json

import pytest

from analysis.report import Layout, Scored, parse_results, render, results_json, sort_runs
from analysis.result import Result, failed, passed, unmeasured

LAYOUT = Layout("interfaces", ["shipped", "terse"], {"oneshot": ["read-before-edit", "help"], "bugfix": ["no-read"]})


def run(rid: str, checks: dict[str, Result], *, timed_out: bool = False) -> Scored:
    variant, task, repeat = rid.split(".")
    return Scored(rid, variant, task, int(repeat), 0, timed_out, 12.5, checks)


RUNS = [
    run("shipped.oneshot.1", {"read-before-edit": passed("read"), "help": passed()}),
    run("shipped.oneshot.2", {"read-before-edit": failed("never read"), "help": unmeasured("no program")}),
    run("shipped.oneshot.3", {"read-before-edit": passed("read"), "help": passed()}, timed_out=True),
    run("terse.oneshot.1", {"read-before-edit": failed("read late"), "help": failed("no example")}),
    run("shipped.bugfix.1", {"no-read": passed("not read")}),
]


def table_row(report: str, task: str, check: str) -> str:
    section = report.split(f"## {task}\n", 1)[1].split("\n## ", 1)[0]
    return next(line for line in section.splitlines() if line.startswith(f"| {check} |"))


def test_render_counts_pass_over_measured_and_unmeasured() -> None:
    report = render(LAYOUT, "2026-11-01T00:00:00Z", RUNS)
    assert table_row(report, "oneshot", "read-before-edit") == "| read-before-edit | 2/3 | 0/1 |"
    assert table_row(report, "oneshot", "help") == "| help | 2/2, 1 unmeasured | 0/1 |"
    assert table_row(report, "bugfix", "no-read") == "| no-read | 1/1 | - |"
    assert "5 runs, 1 killed at the timeout" in report


def test_render_lists_every_check_that_did_not_pass_in_run_order() -> None:
    report = render(LAYOUT, "now", RUNS)
    listed = report.split("## Not passing\n\n", 1)[1].strip().splitlines()
    assert listed == [
        "- `shipped.oneshot.2` read-before-edit: fail: never read",
        "- `shipped.oneshot.2` help: unmeasured: no program",
        "- `terse.oneshot.1` read-before-edit: fail: read late",
        "- `terse.oneshot.1` help: fail: no example",
    ]


def test_render_with_baseline_shows_the_earlier_fraction() -> None:
    baseline = [
        run("shipped.oneshot.1", {"read-before-edit": failed("x"), "help": unmeasured("y")}),
        run("terse.oneshot.1", {"read-before-edit": passed()}),
    ]
    report = render(LAYOUT, "now", RUNS, baseline)
    assert table_row(report, "oneshot", "read-before-edit") == "| read-before-edit | 2/3 (was 0/1) | 0/1 (was 1/1) |"
    assert table_row(report, "oneshot", "help") == "| help | 2/2, 1 unmeasured (was 0/0) | 0/1 |"
    assert table_row(report, "bugfix", "no-read") == "| no-read | 1/1 | - |"


def test_render_adds_variants_tasks_and_checks_missing_from_the_layout() -> None:
    extra = [
        *RUNS,
        run("new.oneshot.1", {"help": passed(), "extra-check": failed("seen")}),
        run("new.other.1", {"x": passed()}),
    ]
    report = render(LAYOUT, "now", extra)
    assert "| check | shipped | terse | new |" in report
    assert table_row(report, "oneshot", "extra-check") == "| extra-check | - | - | 0/1 |"
    assert table_row(report, "other", "x") == "| x | - | - | 1/1 |"
    assert report.index("## oneshot") < report.index("## bugfix") < report.index("## other")


def test_render_when_everything_passes() -> None:
    assert "Every check passed." in render(LAYOUT, "now", [RUNS[0]])


def test_sort_runs_follows_the_layout_then_repeat() -> None:
    shuffled = [
        run("terse.oneshot.1", {}),
        run("shipped.bugfix.1", {}),
        run("shipped.oneshot.10", {}),
        run("shipped.oneshot.2", {}),
    ]
    assert [r.id for r in sort_runs(shuffled, LAYOUT)] == [
        "shipped.oneshot.2",
        "shipped.oneshot.10",
        "shipped.bugfix.1",
        "terse.oneshot.1",
    ]


def test_results_json_round_trips() -> None:
    written = results_json("interfaces", "2026-11-01T00:00:00Z", RUNS)
    assert written["suite"] == "interfaces"
    first = written["runs"][0]  # type: ignore[index]  # a list of dicts
    assert first == {
        "id": "shipped.oneshot.1",
        "variant": "shipped",
        "task": "oneshot",
        "repeat": 1,
        "exitCode": 0,
        "timedOut": False,
        "seconds": 12.5,
        "checks": {"read-before-edit": {"status": "pass", "detail": "read"}, "help": {"status": "pass", "detail": ""}},
    }
    assert parse_results(json.loads(json.dumps(written))) == RUNS


@pytest.mark.parametrize(
    "value",
    [
        [],
        {"runs": "no"},
        {"runs": [{"id": "a", "variant": "v"}]},
        {"runs": [{"id": "a", "variant": "v", "task": "t", "checks": {"c": {"status": "maybe"}}}]},
        {"runs": [{"id": "a", "variant": "v", "task": "t", "checks": {"c": {"status": "fail", "detail": ""}}}]},
    ],
)
def test_parse_results_refuses_what_is_not_results(value: object) -> None:
    with pytest.raises(ValueError, match=r"."):
        parse_results(value)
