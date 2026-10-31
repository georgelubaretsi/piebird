"""A run folder as the runner wrote it, and what checks share while scoring.

One thread scores one run, so a run's lazy values need no lock; the context's cache is shared
between threads and locks per file.
"""

import json
import os
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

from analysis import clicheck, journal
from analysis.program import Finder, Program, changed_files
from analysis.result import Result
from analysis.tools import Tool

XDG = {
    "HOME": "home",
    "XDG_CONFIG_HOME": "config",
    "XDG_DATA_HOME": "data",
    "XDG_STATE_HOME": "state",
    "XDG_CACHE_HOME": "cache",
}


@dataclass
class Context:
    out: Path
    guide: str  # plugin-relative path the read checks look for
    bun: str | None
    temp: Path  # per-run folders: isolated HOME and XDG folders, scratch files
    _locks: dict[str, threading.Lock] = field(default_factory=dict)
    _guard: threading.Lock = field(default_factory=threading.Lock)

    @property
    def cache(self) -> Path:
        return self.out / "cache"

    def env(self, run_id: str) -> dict[str, str]:
        """The caller's environment with a fresh HOME and XDG folders for this run."""
        env = dict(os.environ)
        for key, name in XDG.items():
            folder = self.temp / run_id / name
            folder.mkdir(parents=True, exist_ok=True)
            env[key] = str(folder)
        return env

    def scratch(self, run_id: str) -> Path:
        folder = self.temp / run_id / "scratch"
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def cached(self, name: str, make: Callable[[Path], None]) -> Path:
        """`<out>/cache/<name>`, made once by `make(path)` (written beside it, then renamed)."""
        with self._guard:
            lock = self._locks.setdefault(name, threading.Lock())
        path = self.cache / name
        with lock:
            if not path.exists():
                self.cache.mkdir(parents=True, exist_ok=True)
                partial = path.with_name(f".{name}.{os.getpid()}.partial")
                make(partial)
                partial.replace(path)
        return path


@dataclass(frozen=True, slots=True)
class Meta:
    id: str
    variant: str
    task: str
    repeat: int
    exit_code: int | None
    timed_out: bool
    seconds: float | None
    error: str | None

    @staticmethod
    def parse(value: object) -> Meta:
        """From meta.json; ValueError names the first field that's missing or wrong."""
        if not isinstance(value, dict):
            raise ValueError("meta.json isn't an object")
        text = {k: value.get(k) for k in ("id", "variant", "task")}
        for key, got in text.items():
            if not isinstance(got, str) or not got:
                raise ValueError(f"meta.json: {key} isn't a string")
        repeat, code, seconds, error = (value.get(k) for k in ("repeat", "exitCode", "seconds", "error"))
        if not isinstance(repeat, int) or isinstance(repeat, bool):
            raise ValueError("meta.json: repeat isn't a number")
        return Meta(
            id=str(text["id"]),
            variant=str(text["variant"]),
            task=str(text["task"]),
            repeat=repeat,
            exit_code=code if isinstance(code, int) and not isinstance(code, bool) else None,
            timed_out=value.get("timedOut") is True,
            seconds=float(seconds) if isinstance(seconds, int | float) and not isinstance(seconds, bool) else None,
            error=error if isinstance(error, str) and error else None,
        )


class Run:
    def __init__(self, folder: Path, meta: Meta, ctx: Context) -> None:
        self.folder = folder
        self.meta = meta
        self._ctx = ctx

    @property
    def id(self) -> str:
        return self.meta.id

    @property
    def project(self) -> Path:
        return self.folder / "project"

    @cached_property
    def calls(self) -> list[journal.ToolCall] | None:
        """The journal's tool calls in time order; None without a journal."""
        path = self.folder / "journal.jsonl"
        if not path.is_file():
            return None
        with path.open(encoding="utf-8", errors="replace") as lines:
            return journal.parse_calls(lines)

    @cached_property
    def changed(self) -> list[str]:
        """Files the run added or changed (diff.patch), outside node_modules."""
        path = self.folder / "diff.patch"
        return changed_files(path.read_text(errors="replace")) if path.is_file() else []

    @cached_property
    def env(self) -> dict[str, str]:
        return self._ctx.env(self.id)

    @cached_property
    def program(self) -> Program | str:
        """The program the run built, or a string saying what was looked at."""
        if not self.project.is_dir():
            return "no project folder in the run"
        return Finder(self.project, self.env, self._ctx.bun).find(self.changed)

    @cached_property
    def tools(self) -> list[Tool] | str:
        """The program's `--help --json` tool definitions, or a string saying what it printed."""
        found = self.program
        return found if isinstance(found, str) else clicheck.tool_definitions(found)


type Check = Callable[[Run, Context], Result]
type Checks = Mapping[str, Check]


def load_meta(folder: Path) -> Meta:
    """meta.json of a run folder; OSError or ValueError when it can't be read."""
    return Meta.parse(json.loads((folder / "meta.json").read_text()))
