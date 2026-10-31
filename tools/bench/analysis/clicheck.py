"""Checks of a program's command line: name, help, version, tool definitions, errors, JSON input."""

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass

from analysis.program import Completed, Program, read_package
from analysis.result import Result, excerpt, failed, passed, unmeasured
from analysis.tools import Tool, parse_tools, sampled

EXAMPLE = re.compile(r"(?i)example|e\.g\.|^\s*\$ ", re.MULTILINE)
USAGE = re.compile(r"(?im)^\s*usage:\s*([a-z][a-z0-9-]*)\b")
RUNNERS = frozenset({"bun", "node", "npx", "bunx", "deno"})
GENERIC_SCRIPTS = frozenset({"test", "start", "dev", "build", "lint", "check", "fmt", "format", "typecheck"})
BAD_FLAG = "--definitely-not-a-flag"
BOGUS = '{"bogus": 1}'


def named(program: Program) -> Result:
    """A real name: a package.json bin or script, or the program named in its usage line."""
    package = read_package(program.project)
    for key in ("bin", "scripts"):
        value = package.get(key)
        if isinstance(value, dict):
            names = [k for k in value if k not in GENERIC_SCRIPTS]
            if names:
                return passed(f"{names[0]} (package.json {key})")
        if key == "bin" and isinstance(value, str) and isinstance(package.get("name"), str):
            return passed(f"{package['name']} (package.json name, bin {value})")
    text = program.run(["--help"]).text()
    usage = USAGE.search(text)
    if usage and usage.group(1) not in RUNNERS:
        return passed(f"{usage.group(1)} (usage line of --help; no package.json bin)")
    return failed(f"no package.json bin or script name; --help usage: {excerpt(_usage_line(text))}")


def help_text(program: Program) -> Result:
    done = program.run(["--help"])
    text = done.text()
    if done.exit_code != 0:
        return failed(f"--help {done.exit_text}: {excerpt(text)}")
    if not EXAMPLE.search(text):
        return failed(f"--help has no example ('example', 'e.g.' or a '$ ' line): {excerpt(text)}")
    return passed()


def version(program: Program) -> Result:
    done = program.run(["--version"])
    if done.exit_code != 0 or not done.stdout.strip():
        return failed(f"--version {done.exit_text}, stdout {excerpt(done.stdout)}, stderr {excerpt(done.stderr)}")
    return passed(excerpt(done.stdout, 60))


def tool_definitions(program: Program) -> list[Tool] | str:
    """`--help --json` as tool definitions (it must exit 0), or a string saying what it printed."""
    done = program.run(["--help", "--json"])
    if done.exit_code != 0:
        return f"--help --json {done.exit_text}, stdout {excerpt(done.stdout)}, stderr {excerpt(done.stderr)}"
    try:
        value: object = json.loads(done.stdout)
    except ValueError:
        return f"--help --json {done.exit_text}, stdout isn't JSON: {excerpt(done.text())}"
    tools = parse_tools(value)
    return f"--help --json printed {tools}" if isinstance(tools, str) else tools


def help_json(tools: list[Tool] | str) -> Result:
    if isinstance(tools, str):
        return failed(tools)
    return passed(f"{len(tools)} tools: {', '.join(t.name for t in tools)}")


def bad_flag(program: Program) -> Result:
    done = program.run([BAD_FLAG])
    if done.exit_code == 2 and not done.stdout.strip():
        return passed(f"exit 2, stderr {excerpt(done.stderr, 80)}")
    return failed(f"{BAD_FLAG}: {done.exit_text}, stdout {excerpt(done.stdout)}, stderr {excerpt(done.stderr)}")


@dataclass(frozen=True, slots=True)
class _Outcome:
    tool: str
    words: list[str] | None  # the command words found; None: not mapped
    problem: str | None = None  # set for a failure

    def via(self) -> str:
        return " ".join(self.words) if self.words else "(no command words)"


def cli_input(program: Program, tools: list[Tool] | str) -> Result:
    """Each tool through `<words> --json --input -`: valid input → exit 0 and one JSON value;
    `{"bogus": 1}` → exit 2, nothing on stdout, a JSON error on stderr.

    A tool maps to the first candidate words (word_candidates) that take its valid input; failing
    that, to words --help names, then, for a program with one tool, to no words at all. A tool
    mapped only those last two ways fails; one that maps nowhere is left out."""
    if isinstance(tools, str):
        return unmeasured(f"no tool definitions: {tools}")
    usage = program.run(["--help"]).text()
    outcomes = [_probe_tool(program, tool, (usage, len(tools) == 1)) for tool in tools]
    problems = [o for o in outcomes if o.problem]
    mapped = [o for o in outcomes if o.words is not None and not o.problem]
    unmapped = [o.tool for o in outcomes if o.words is None and not o.problem]
    if problems:
        more = f" (and {len(problems) - 1} more)" if len(problems) > 1 else ""
        return failed(f"{problems[0].tool} via `{problems[0].via()}`: {problems[0].problem}{more}")
    if not mapped:
        tried = "; ".join(f"{t.name}: {' | '.join(' '.join(w) or '-' for w in word_candidates(t.name))}" for t in tools)
        return unmeasured(f"no tool maps to a command (tried {tried})")
    note = f"; not mapped: {', '.join(unmapped)}" if unmapped else ""
    return passed(", ".join(f"{o.tool} via `{o.via()}`" for o in mapped) + note)


def word_candidates(name: str) -> list[list[str]]:
    """Command words a tool name may map to: whole, split on `_` or `-`, kebab-case, without a
    program prefix (`cart_total` → `total`), none at all."""
    under, dash = name.split("_"), name.split("-")
    kebab = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", name).replace("_", "-").lower()
    found = [[name], under, dash, *([under[1:]] if len(under) > 1 else []), [kebab], kebab.split("-"), []]
    unique: list[list[str]] = []
    for words in found:
        clean = [w for w in words if w]
        if clean not in unique:
            unique.append(clean)
    return unique


def _probe_tool(program: Program, tool: Tool, hints: tuple[str, bool]) -> _Outcome:
    """`hints`: the --help text, and whether this is the program's only tool."""
    usage, alone = hints
    good = json.dumps(sampled(tool)("cli").args)
    attempts: list[tuple[list[str], Completed]] = []
    for words in word_candidates(tool.name):
        done = program.run([*words, "--json", "--input", "-"], stdin=good)
        if done.exit_code == 0 and _is_result(done.stdout):
            return _bogus(program, tool, words)
        attempts.append((words, done))
    in_help = [(w, d) for w, d in attempts if w and _mentions(usage, w)]
    likely = in_help or [(w, d) for w, d in attempts if not w and alone]
    if not likely:
        return _Outcome(tool.name, None)
    words, done = likely[0]
    problem = f"valid input {excerpt(good, 100)} → {done.exit_text}, stdout {excerpt(done.stdout)}, stderr {excerpt(done.stderr)}"
    return _Outcome(tool.name, words, problem)


def _bogus(program: Program, tool: Tool, words: list[str]) -> _Outcome:
    if not tool.rejects_bogus():
        return _Outcome(tool.name, words)  # the schema accepts it: nothing to check
    done = program.run([*words, "--json", "--input", "-"], stdin=BOGUS)
    error = _json_error(done.stderr)
    if done.exit_code == 2 and not done.stdout.strip() and error:
        return _Outcome(tool.name, words)
    seen = f"{done.exit_text}, stdout {excerpt(done.stdout)}, stderr {excerpt(done.stderr)}"
    want = "" if error else " (stderr has no {error: {code, message}})"
    return _Outcome(tool.name, words, f"{BOGUS} → {seen}{want}")


def _json_error(stderr: str) -> bool:
    """Whether stderr (whole, or its last line) is `{"error": {"code": …, "message": …}}`."""
    lines = stderr.strip().splitlines()
    for text in (stderr, lines[-1] if lines else ""):
        try:
            value: object = json.loads(text)
        except ValueError:
            continue
        error = value.get("error") if isinstance(value, dict) else None
        if isinstance(error, dict) and {"code", "message"} <= error.keys():
            return True
    return False


def _is_result(stdout: str) -> bool:
    """One JSON value that isn't the tool definitions (a bare command may print those)."""
    try:
        value: object = json.loads(stdout)
    except ValueError:
        return False
    if isinstance(value, dict) and "tools" in value:
        return False
    return '"inputSchema"' not in json.dumps(value)


def _mentions(text: str, words: Sequence[str]) -> bool:
    phrase = r"\s+".join(re.escape(w) for w in words)
    return re.search(rf"(?<![\w-]){phrase}(?![\w-])", text) is not None


def _usage_line(text: str) -> str:
    return next((line for line in text.splitlines() if "usage" in line.lower()), text[:80])
