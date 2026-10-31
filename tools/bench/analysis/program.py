"""The program a run built: where it is, how to start it, and running it with a timeout.

Found in this order: package.json `bin` (its first entry); else a changed TypeScript file that
reads its arguments (`import.meta.main`, `Bun.argv`, `process.argv`), one with `cli` in its name
first, then the shortest; else a changed TypeScript file whose `--help --json` prints tool
definitions. `.ts`/`.js`/`.mjs`/`.cjs` entries run with bun, anything else directly.
"""

import contextlib
import json
import os
import re
import signal
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from analysis.tools import parse_tools

BUN_SUFFIXES = (".ts", ".tsx", ".mts", ".cts", ".js", ".mjs", ".cjs")
MAIN_MARK = re.compile(r"import\.meta\.main|Bun\.argv|process\.argv")
CHANGED = re.compile(r"^\+\+\+ b/(\S+)", re.MULTILINE)
KILL_WAIT = 5.0


@dataclass(frozen=True, slots=True)
class Command:
    argv: tuple[str, ...]
    cwd: Path
    env: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class Completed:
    exit_code: int | None  # None: killed at the timeout
    stdout: str
    stderr: str
    seconds: float

    @property
    def exit_text(self) -> str:
        return "timed out" if self.exit_code is None else f"exit {self.exit_code}"

    def text(self) -> str:
        """What the program printed: stdout, or stderr when stdout is empty."""
        return self.stdout if self.stdout.strip() else self.stderr


def execute(command: Command, stdin: str = "", timeout: float = 30.0) -> Completed:
    """Runs to completion or `timeout`; the whole process group is killed either way."""
    start = time.monotonic()
    proc = subprocess.Popen(
        command.argv,
        cwd=command.cwd,
        env=dict(command.env),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        out, err = proc.communicate(stdin.encode(), timeout=timeout)
        code: int | None = proc.returncode
    except subprocess.TimeoutExpired:
        kill_group(proc)
        try:
            out, err = proc.communicate(timeout=KILL_WAIT)
        except subprocess.TimeoutExpired:  # a descendant outside the group holds the pipes
            out, err = b"", b""
        code = None
    finally:
        kill_group(proc)
    return Completed(code, _text(out), _text(err), time.monotonic() - start)


def kill_group(proc: subprocess.Popen[bytes]) -> None:
    with contextlib.suppress(ProcessLookupError, PermissionError):  # already gone
        os.killpg(proc.pid, signal.SIGKILL)


@dataclass(frozen=True, slots=True)
class Program:
    project: Path
    argv: tuple[str, ...]  # how to start it, before its own arguments
    entry: str  # project-relative
    how: str  # how it was found, for details
    env: Mapping[str, str]

    def command(self, args: Sequence[str]) -> Command:
        return Command((*self.argv, *args), self.project, self.env)

    def run(self, args: Sequence[str], stdin: str = "", timeout: float = 30.0) -> Completed:
        return execute(self.command(args), stdin, timeout)


@dataclass(frozen=True, slots=True)
class Finder:
    project: Path
    env: Mapping[str, str]
    bun: str | None

    def find(self, changed: Sequence[str]) -> Program | str:
        """The program, or a string saying what was looked at."""
        bin_entry = package_bin(self.project)
        if bin_entry is not None and (self.project / bin_entry[1]).is_file():
            return self.program(bin_entry[1], f"package.json bin {bin_entry[0]}")
        sources = [f for f in changed if f.endswith(BUN_SUFFIXES) and ".test." not in f]
        sources = [f for f in sources if (self.project / f).is_file()]
        mains = sorted((f for f in sources if MAIN_MARK.search(_read(self.project / f))), key=_main_rank)
        if mains:
            return self.program(mains[0], "changed file reading argv")
        for source in sources:
            found = self.program(source, "changed file printing tool definitions")
            if isinstance(found, Program) and _prints_tools(found):
                return found
        why = f"package.json bin {bin_entry[1]} missing" if bin_entry else "no package.json bin"
        return f"no program: {why}; {len(sources)} changed source files, none reads argv or prints tools"

    def program(self, entry: str, how: str) -> Program | str:
        if entry.endswith(BUN_SUFFIXES):
            if self.bun is None:
                return f"{entry} needs bun, which isn't on PATH"
            return Program(self.project, (self.bun, entry), entry, how, self.env)
        return Program(self.project, (str(self.project / entry),), entry, how, self.env)


def package_bin(project: Path) -> tuple[str, str] | None:
    """(name, project-relative path) of package.json's first `bin`, if any."""
    package = read_package(project)
    found = package.get("bin")
    if isinstance(found, str):
        name = package.get("name")
        return (name if isinstance(name, str) else found, _relative(found))
    if isinstance(found, dict):
        first = next(((k, v) for k, v in found.items() if isinstance(v, str)), None)
        if first:
            return (first[0], _relative(first[1]))
    return None


def read_package(project: Path) -> dict[str, object]:
    try:
        value: object = json.loads((project / "package.json").read_text())
    except OSError, ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def changed_files(diff: str) -> list[str]:
    """Files a diff adds or changes, outside node_modules."""
    return [f for f in CHANGED.findall(diff) if "node_modules/" not in f]


def _prints_tools(program: Program) -> bool:
    done = program.run(["--help", "--json"], timeout=20)
    try:
        value: object = json.loads(done.stdout)
    except ValueError:
        return False
    return not isinstance(parse_tools(value), str)


def _main_rank(path: str) -> tuple[int, int]:
    return (0 if "cli" in path.lower() else 1, len(path))


def _relative(path: str) -> str:
    return path.removeprefix("./")


def _read(path: Path) -> str:
    try:
        return path.read_text(errors="replace")
    except OSError:
        return ""


def _text(data: bytes | None) -> str:
    return (data or b"").decode(errors="replace")
