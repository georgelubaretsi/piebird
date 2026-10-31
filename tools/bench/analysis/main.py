"""score.py's command line: scores the runs of a bench folder into results.json and report.md.

Exit 0 when scoring ran (whatever the checks found), 2 on bad input (no such folder, a check name
the suite's CHECKS lacks, an unknown run id), 1 on any other failure. `--only` rescores some runs
and keeps the other runs' results from the existing results.json.
"""

import argparse
import importlib.util
import json
import shutil
import sys
import tempfile
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from analysis.model import Check, Checks, Context, Run, load_meta
from analysis.report import Layout, Scored, parse_results, render, results_json
from analysis.result import Result, unmeasured


class BadInputError(Exception):
    """Input the user has to fix: exit 2."""


@dataclass(frozen=True, slots=True)
class Job:
    out: Path
    layout: Layout
    guide: str
    checks: Checks
    runs: list[tuple[Path, str]]  # run folder, task
    baseline: list[Scored] | None
    kept: list[Scored]  # earlier results kept under --only


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        job = load_job(args)
    except BadInputError as err:
        print(f"score.py: {err}", file=sys.stderr)
        return 2
    temp = Path(tempfile.mkdtemp(prefix="bench-score-"))
    try:
        ctx = Context(out=job.out, guide=job.guide, bun=shutil.which("bun"), temp=temp)
        scored = score_all(job, ctx, args.jobs)
    finally:
        shutil.rmtree(temp, ignore_errors=True)
    scored_at = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    runs = job.kept + scored
    (job.out / "results.json").write_text(json.dumps(results_json(job.layout.suite, scored_at, runs), indent=2) + "\n")
    report = render(job.layout, scored_at, runs, job.baseline)
    (job.out / "report.md").write_text(report)
    print(report, end="")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="score.py",
        description="Score a bench folder's runs: writes results.json and report.md there and prints the report.",
        epilog="example:\n  uv run --locked python tools/bench/score.py --jobs 6 -- /tmp/bench-out",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--baseline", type=Path, help="an earlier results.json: cells show `(was p/n)`")
    parser.add_argument("--only", help="run ids to rescore, comma-separated; other runs keep their results")
    parser.add_argument("--jobs", type=_positive, default=4, help="runs scored at once (default 4)")
    parser.add_argument("out", type=Path, help="the bench folder run.ts wrote")
    return parser


def load_job(args: argparse.Namespace) -> Job:
    # Absolute: probes run inside each run's project folder, where a relative path means something else.
    out: Path = args.out.resolve()
    suite = _read_json(out / "suite.json", "suite file")
    if not isinstance(suite, dict):
        raise BadInputError(f"{out / 'suite.json'} isn't an object")
    root = Path(str(suite.get("root", "")))
    tasks = _task_checks(suite)
    ran = suite.get("ran")
    ran_variants = ran.get("variants") if isinstance(ran, dict) else None
    variants = ran_variants if isinstance(ran_variants, list) else list(suite.get("variants") or {})
    layout = Layout(str(suite.get("name") or root.name), [str(v) for v in variants], tasks)
    checks = load_checks(root / "checks.py")
    runs = _select(_run_folders(out), args.only)
    _check_names(runs, tasks, checks)
    baseline = parse_results_file(args.baseline) if args.baseline else None
    kept = _kept(out, {f.name for f, _ in runs}) if args.only else []
    return Job(out, layout, str(suite.get("guide", "")), checks, runs, baseline, kept)


def load_checks(path: Path) -> Checks:
    """`CHECKS` of a suite's checks.py, imported by path."""
    if not path.is_file():
        raise BadInputError(f"no checks file: {path}")
    name = f"bench_checks_{path.parent.name.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise BadInputError(f"can't import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    checks = getattr(module, "CHECKS", None)
    if not isinstance(checks, Mapping):
        raise BadInputError(f"{path} has no CHECKS mapping")
    return checks


def parse_results_file(path: Path) -> list[Scored]:
    try:
        return parse_results(_read_json(path, "baseline"))
    except ValueError as err:
        raise BadInputError(f"{path}: {err}") from err


def score_all(job: Job, ctx: Context, jobs: int) -> list[Scored]:
    """Every selected run, `jobs` at a time; each run's checks in order, in one thread."""
    pool = ThreadPoolExecutor(max_workers=jobs)
    futures = {
        pool.submit(score_run, folder, job.checks, job.layout.tasks.get(task, []), ctx): folder
        for folder, task in job.runs
    }
    scored: list[Scored] = []
    try:
        for done, future in enumerate(as_completed(futures), start=1):
            scored.append(future.result())
            print(f"scored {futures[future].name} ({done}/{len(futures)})", file=sys.stderr)
    except BaseException:
        pool.shutdown(wait=False, cancel_futures=True)
        raise
    pool.shutdown()
    return scored


def score_run(folder: Path, checks: Checks, names: list[str], ctx: Context) -> Scored:
    meta = load_meta(folder)
    run = Run(folder, meta, ctx)
    try:
        results = {
            n: unmeasured(f"the run failed: {meta.error}") if meta.error else run_check(checks[n], run, ctx)
            for n in names
        }
    finally:
        shutil.rmtree(ctx.temp / meta.id, ignore_errors=True)
    return Scored(meta.id, meta.variant, meta.task, meta.repeat, meta.exit_code, meta.timed_out, meta.seconds, results)


def run_check(check: Check, run: Run, ctx: Context) -> Result:
    """A check's result; one that raises is unmeasured, with the exception."""
    try:
        result = check(run, ctx)
    except Exception as err:  # contract: a raising check is unmeasured, never a crash
        return unmeasured(f"check raised {type(err).__name__}: {err}")
    if not isinstance(result, Result):
        return unmeasured(f"check returned {type(result).__name__}, not a Result")
    return result


def _task_checks(suite: Mapping[str, object]) -> dict[str, list[str]]:
    tasks = suite.get("tasks")
    if not isinstance(tasks, dict):
        raise BadInputError("suite.json has no tasks object")
    found: dict[str, list[str]] = {}
    for name, task in tasks.items():
        checks = task.get("checks") if isinstance(task, dict) else None
        if not isinstance(checks, list) or not all(isinstance(c, str) for c in checks):
            raise BadInputError(f"suite.json task {name}: checks isn't a list of names")
        found[str(name)] = [str(c) for c in checks]
    return found


def _run_folders(out: Path) -> list[tuple[Path, str]]:
    """(folder, task) of each run with a readable meta.json; the others are skipped with a warning."""
    runs_dir = out / "runs"
    if not runs_dir.is_dir():
        raise BadInputError(f"no runs folder: {runs_dir}")
    found: list[tuple[Path, str]] = []
    for folder in sorted(p for p in runs_dir.iterdir() if p.is_dir()):
        try:
            found.append((folder, load_meta(folder).task))
        except (OSError, ValueError) as err:
            print(f"score.py: skipping {folder.name}: {err}", file=sys.stderr)
    return found


def _select(runs: list[tuple[Path, str]], only: str | None) -> list[tuple[Path, str]]:
    if not only:
        return runs
    wanted = {w.strip() for w in only.split(",") if w.strip()}
    unknown = wanted - {f.name for f, _ in runs}
    if unknown:
        raise BadInputError(f"no such run: {', '.join(sorted(unknown))}")
    return [(f, t) for f, t in runs if f.name in wanted]


def _check_names(runs: list[tuple[Path, str]], tasks: Mapping[str, list[str]], checks: Checks) -> None:
    used = sorted({t for _, t in runs})
    unknown_tasks = [t for t in used if t not in tasks]
    if unknown_tasks:
        raise BadInputError(f"runs of tasks the suite lacks: {', '.join(unknown_tasks)}")
    missing = sorted({n for t in used for n in tasks[t] if n not in checks})
    if missing:
        raise BadInputError(f"checks the suite's CHECKS lacks: {', '.join(missing)}")


def _kept(out: Path, rescored: set[str]) -> list[Scored]:
    path = out / "results.json"
    if not path.is_file():
        return []
    try:
        earlier = parse_results(json.loads(path.read_text()))
    except ValueError as err:
        print(f"score.py: {path} unreadable ({err}); writing only the rescored runs", file=sys.stderr)
        return []
    return [r for r in earlier if r.id not in rescored]


def _read_json(path: Path, what: str) -> object:
    try:
        value: object = json.loads(path.read_text())
    except FileNotFoundError as err:
        raise BadInputError(f"no {what}: {path}") from err
    except (OSError, ValueError) as err:
        raise BadInputError(f"{what} {path}: {err}") from err
    return value


def _positive(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be 1 or more")
    return value
