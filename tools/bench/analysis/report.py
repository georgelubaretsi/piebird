"""results.json and report.md from scored runs (pure)."""

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from analysis.result import Result, Status


@dataclass(frozen=True, slots=True)
class Scored:
    id: str
    variant: str
    task: str
    repeat: int
    exit_code: int | None
    timed_out: bool
    seconds: float | None
    checks: dict[str, Result] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Layout:
    """The suite, and the order tables follow: variants (columns), tasks and their checks (rows)."""

    suite: str
    variants: list[str]
    tasks: dict[str, list[str]]


type Cell = tuple[str, str, str]  # variant, task, check
type Counts = Mapping[tuple[Cell, Status], int]


def results_json(suite: str, scored_at: str, runs: Sequence[Scored]) -> dict[str, object]:
    return {
        "suite": suite,
        "scoredAt": scored_at,
        "runs": [
            {
                "id": r.id,
                "variant": r.variant,
                "task": r.task,
                "repeat": r.repeat,
                "exitCode": r.exit_code,
                "timedOut": r.timed_out,
                "seconds": r.seconds,
                "checks": {name: {"status": str(res.status), "detail": res.detail} for name, res in r.checks.items()},
            }
            for r in runs
        ],
    }


def parse_results(value: object) -> list[Scored]:
    """The runs of a results.json; ValueError when it isn't one."""
    runs = value.get("runs") if isinstance(value, dict) else None
    if not isinstance(runs, list):
        raise ValueError("not a results.json: no runs list")
    return [_parse_run(item, i) for i, item in enumerate(runs, start=1)]


def sort_runs(runs: Sequence[Scored], layout: Layout) -> list[Scored]:
    tasks = list(layout.tasks)
    return sorted(
        runs, key=lambda r: (_index(layout.variants, r.variant), r.variant, _index(tasks, r.task), r.task, r.repeat)
    )


def render(layout: Layout, scored_at: str, runs: Sequence[Scored], baseline: Sequence[Scored] | None = None) -> str:
    """One table per task (rows: checks, columns: variants), then every check that didn't pass."""
    runs = sort_runs(runs, layout)
    counts = _counts(runs)
    before = _counts(baseline) if baseline is not None else None
    variants = _ordered(layout.variants, [r.variant for r in runs])
    lines = [f"# Bench: {layout.suite}", "", _summary(scored_at, runs), ""]
    for task in _ordered(list(layout.tasks), [r.task for r in runs]):
        names = _ordered(layout.tasks.get(task, []), [n for r in runs if r.task == task for n in r.checks])
        lines += [f"## {task}", "", "| check | " + " | ".join(variants) + " |", "| --- |" + " --- |" * len(variants)]
        for name in names:
            cells = [_cell(counts, before, (v, task, name)) for v in variants]
            lines.append(f"| {name} | " + " | ".join(cells) + " |")
        lines.append("")
    lines += ["## Not passing", ""]
    failing = [(r, n, res) for r in runs for n, res in r.checks.items() if res.status is not Status.PASS]
    lines += [f"- `{r.id}` {n}: {res.status}: {res.detail}" for r, n, res in failing] or ["Every check passed."]
    return "\n".join(lines) + "\n"


def _summary(scored_at: str, runs: Sequence[Scored]) -> str:
    timed_out = sum(r.timed_out for r in runs)
    late = f", {timed_out} killed at the timeout" if timed_out else ""
    return f"Scored {scored_at}: {len(runs)} runs{late}. Cells: pass/(pass+fail), then any unmeasured."


def _counts(runs: Sequence[Scored]) -> Counter[tuple[Cell, Status]]:
    return Counter(((r.variant, r.task, name), res.status) for r in runs for name, res in r.checks.items())


def _cell(counts: Counts, before: Counts | None, cell: Cell) -> str:
    shown = _fraction(counts, cell)
    if shown is None:
        return "-"
    was = _fraction(before, cell, with_unmeasured=False) if before is not None else None
    return shown + (f" (was {was})" if was else "")


def _fraction(counts: Counts, cell: Cell, *, with_unmeasured: bool = True) -> str | None:
    p, f, u = (counts.get((cell, s), 0) for s in (Status.PASS, Status.FAIL, Status.UNMEASURED))
    if p + f + u == 0:
        return None
    return f"{p}/{p + f}" + (f", {u} unmeasured" if u and with_unmeasured else "")


def _ordered(first: Sequence[str], seen: Sequence[str]) -> list[str]:
    """`first` in its order (those seen), then anything else seen, in order of appearance."""
    present = set(seen)
    rest = [s for s in dict.fromkeys(seen) if s not in first]
    return [f for f in first if f in present] + rest


def _index(items: Sequence[str], item: str) -> int:
    return items.index(item) if item in items else len(items)


def _parse_run(item: object, n: int) -> Scored:
    if not isinstance(item, dict):
        raise ValueError(f"run {n} isn't an object")
    if not all(isinstance(item.get(k), str) for k in ("id", "variant", "task")) or not isinstance(
        item.get("checks"), dict
    ):
        raise ValueError(f"run {n} lacks id, variant, task or checks")
    checks: dict[str, Result] = {}
    for name, value in item["checks"].items():
        status = value.get("status") if isinstance(value, dict) else None
        if status not in {str(s) for s in Status}:
            raise ValueError(f"run {n} check {name}: status {status!r}")
        detail = value.get("detail")
        checks[str(name)] = Result(Status(str(status)), detail if isinstance(detail, str) else "")
    code, seconds, repeat = item.get("exitCode"), item.get("seconds"), item.get("repeat")
    return Scored(
        id=item["id"],
        variant=item["variant"],
        task=item["task"],
        repeat=repeat if isinstance(repeat, int) else 0,
        exit_code=code if isinstance(code, int) else None,
        timed_out=item.get("timedOut") is True,
        seconds=float(seconds) if isinstance(seconds, int | float) else None,
        checks=checks,
    )
