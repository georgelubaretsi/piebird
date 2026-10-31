import json
from pathlib import Path

import pytest

from analysis.main import main

CHECKS = """
from analysis.result import failed, passed


def boom(run, ctx):
    raise RuntimeError("probe broke")


CHECKS = {
    "journal": lambda run, ctx: passed(f"{len(run.calls or [])} calls") if run.calls else failed("no calls"),
    "guide": lambda run, ctx: passed(ctx.guide),
    "boom": boom,
    "odd": lambda run, ctx: "not a result",
    "paths": lambda run, ctx: (
        passed("absolute") if run.project.is_absolute() and ctx.cache.is_absolute() else failed(f"{run.project}")
    ),
}
"""


def make_out(tmp_path: Path, checks: list[str], runs: dict[str, dict[str, object]]) -> Path:
    root = tmp_path / "suite"
    root.mkdir()
    (root / "checks.py").write_text(CHECKS)
    out = tmp_path / "out"
    suite = {
        "name": "demo",
        "root": str(root),
        "guide": "rules/demo.md",
        "variants": {"a": {}, "b": {}},
        "tasks": {"t": {"prompt": "p", "checks": checks}},
        "ran": {"variants": ["a", "b"], "tasks": ["t"], "repeats": 1},
    }
    (out / "runs").mkdir(parents=True)
    (out / "suite.json").write_text(json.dumps(suite))
    for rid, extra in runs.items():
        variant, task, repeat = rid.split(".")
        folder = out / "runs" / rid
        folder.mkdir()
        meta = {
            "id": rid,
            "variant": variant,
            "task": task,
            "repeat": int(repeat),
            "exitCode": 0,
            "timedOut": False,
            "seconds": 3,
        }
        (folder / "meta.json").write_text(json.dumps(meta | extra))
        call = {
            "type": "message",
            "message": {"content": [{"type": "toolCall", "name": "read", "arguments": {"path": "x"}}]},
        }
        (folder / "journal.jsonl").write_text(json.dumps(call) + "\n")
    return out


def results(out: Path) -> dict[str, dict[str, dict[str, str]]]:
    written = json.loads((out / "results.json").read_text())
    return {r["id"]: r["checks"] for r in written["runs"]}


def test_main_gives_checks_absolute_paths_for_a_relative_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    make_out(tmp_path, ["paths"], {"a.t.1": {}})
    monkeypatch.chdir(tmp_path)
    assert main(["--", "out"]) == 0
    assert results(tmp_path / "out")["a.t.1"]["paths"]["status"] == "pass"


def test_main_scores_runs_and_writes_both_files(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = make_out(tmp_path, ["journal", "guide", "boom", "odd"], {"a.t.1": {}, "b.t.1": {"error": "sandbox failed"}})
    assert main(["--jobs", "2", "--", str(out)]) == 0
    got = results(out)
    assert got["a.t.1"] == {
        "journal": {"status": "pass", "detail": "1 calls"},
        "guide": {"status": "pass", "detail": "rules/demo.md"},
        "boom": {"status": "unmeasured", "detail": "check raised RuntimeError: probe broke"},
        "odd": {"status": "unmeasured", "detail": "check returned str, not a Result"},
    }
    assert {c["status"] for c in got["b.t.1"].values()} == {"unmeasured"}
    assert got["b.t.1"]["journal"]["detail"] == "the run failed: sandbox failed"
    report = (out / "report.md").read_text()
    assert "| journal | 1/1 | 0/0, 1 unmeasured |" in report
    assert capsys.readouterr().out == report


def test_main_refuses_unknown_checks_before_scoring(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = make_out(tmp_path, ["journal", "no-such-check"], {"a.t.1": {}})
    assert main([str(out)]) == 2
    assert "no-such-check" in capsys.readouterr().err
    assert not (out / "results.json").exists()


@pytest.mark.parametrize(
    "args",
    [["--only", "a.t.9"], ["--baseline", "missing.json"]],
)
def test_main_refuses_bad_input(tmp_path: Path, args: list[str]) -> None:
    out = make_out(tmp_path, ["journal"], {"a.t.1": {}})
    assert main([*args, "--", str(out)]) == 2
    assert not (out / "results.json").exists()


def test_main_refuses_a_missing_folder(tmp_path: Path) -> None:
    assert main(["--", str(tmp_path / "nothing")]) == 2


def test_main_skips_run_folders_without_meta(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = make_out(tmp_path, ["journal"], {"a.t.1": {}})
    (out / "runs" / "a.t.2").mkdir()
    assert main([str(out)]) == 0
    assert list(results(out)) == ["a.t.1"]
    assert "skipping a.t.2" in capsys.readouterr().err


def test_main_only_rescores_some_runs_and_keeps_the_rest(tmp_path: Path) -> None:
    out = make_out(tmp_path, ["journal"], {"a.t.1": {}, "b.t.1": {}})
    assert main([str(out)]) == 0
    (out / "runs" / "b.t.1" / "journal.jsonl").write_text("")
    assert main(["--only", "b.t.1", "--", str(out)]) == 0
    got = results(out)
    assert got["a.t.1"]["journal"]["status"] == "pass"
    assert got["b.t.1"]["journal"] == {"status": "fail", "detail": "no calls"}


def test_main_with_baseline(tmp_path: Path) -> None:
    out = make_out(tmp_path, ["journal"], {"a.t.1": {}})
    assert main([str(out)]) == 0
    baseline = tmp_path / "baseline.json"
    (out / "results.json").rename(baseline)
    assert main(["--baseline", str(baseline), "--", str(out)]) == 0
    assert "| journal | 1/1 (was 1/1) |\n" in (out / "report.md").read_text()
