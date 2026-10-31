"""The interfaces suite's checks: whether the agent reads the rule before building, and whether
the program it builds keeps the rule's contract (CLI, rpc and mcp modes, sessions, progress,
cancellation) in the suite's cart domain.

Operations are found from the program's own tool definitions, by name and argument words: an add
and a show operation for sessions; for the slow task, the re-pricing one with a source file and an
output file argument (a tool named for prices first). Nothing is fixed per run.
"""

import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from analysis import clicheck, journal, longops, probes
from analysis.model import Check, Context, Run
from analysis.program import Program
from analysis.result import Result, failed, passed, unmeasured
from analysis.rpcio import LineRpc, describe, has_result
from analysis.schema import Json, sample
from analysis.tools import Call, MakeCall, Tool, pick_call, words

FINISH_TIMEOUT = 300.0
BIG_EXPORT = ("big-export.jsonl", 4_000_000)
SMALL_EXPORT = ("small-export.jsonl", 3)
CART = (
    '{{"id":"c{i}","lines":[{{"price":12,"qty":2}},{{"price":5,"qty":1}}],"giftCard":10,"shippingBase":6,"coupon":2}}\n'
)
SOURCE_WORDS = frozenset(
    {"source", "src", "input", "in", "from", "export", "exports", "cart", "carts", "file", "path", "jsonl"}
)
OUTPUT_WORDS = frozenset({"output", "out", "dest", "destination", "target", "result", "results", "write", "to"})
PRICE_WORDS = frozenset({"price", "prices", "reprice", "repricing", "pricing"})
ID_KEY = re.compile(r"(?i)^(?:(?:cart|session)(?:[_-]?id)?|id)$")
ITEM_WORDS = frozenset({"sku", "name", "item", "product", "title", "label", "code"})
MONEY_WORDS = frozenset({"price", "amount", "qty", "quantity", "total", "cost", "count"})
SHOW_WORDS = frozenset({"show", "get", "view", "summary", "list", "status", "state"})
TOTAL_WORDS = frozenset({"total", "totals"})  # weaker: a stateless `total` may take the lines as input
CHANGE_WORDS = frozenset({"add", "remove", "delete", "apply", "set", "clear", "reset", "update"})
CREATE_WORDS = frozenset({"new", "create", "open", "start", "begin"})
ITEMS = ("tee", "mug")


@dataclass(frozen=True, slots=True)
class Reprice:
    """The re-pricing operation and its file arguments."""

    tool: Tool
    source: str
    output: str

    def call(self, source: Path, output: Path) -> Call:
        args = _object(sample(self.tool.input_schema))
        return Call(self.tool.name, {**args, self.source: str(source), self.output: str(output)})

    def maker(self, source: Path, folder: Path) -> MakeCall:
        return lambda tag: self.call(source, folder / f"{tag}.jsonl")


def find_reprice(tools: Sequence[Tool]) -> Reprice | str:
    """The tool taking a source file and an output file, one named for prices first."""
    found = [r for r in (_file_arguments(t) for t in tools) if r is not None]
    if not found:
        return f"no tool takes a source file and an output file: {'; '.join(t.signature() for t in tools)}"
    priced = [r for r in found if PRICE_WORDS & set(words(r.tool.name))]
    return (priced or found)[0]


def item_key(add: Tool) -> str | None:
    """The add operation's string argument naming the item (sku, name, ...)."""
    keys = [k for k in add.string_properties() if not ID_KEY.match(k) and not MONEY_WORDS & set(words(k))]
    return next((k for k in keys if ITEM_WORDS & set(words(k))), keys[0] if keys else None)


def show_tool(tools: Sequence[Tool], add: Tool) -> Tool | None:
    """The operation showing the cart: a show/get word (or, weaker, total), no change word; least
    input first."""

    def named(tool: Tool, kinds: frozenset[str]) -> bool:
        return bool(kinds & set(words(tool.name)))

    shows = [t for t in tools if t is not add and named(t, SHOW_WORDS | TOTAL_WORDS) and not named(t, CHANGE_WORDS)]
    return min(shows, key=lambda t: (not named(t, SHOW_WORDS), len(t.required())), default=None)


def cart_id(result: object) -> str | int | None:
    """A cart or session id in a result: a top-level key like cartId, or one object deep."""
    if not isinstance(result, Mapping):
        return None
    for key, value in result.items():
        if ID_KEY.match(str(key)) and isinstance(value, str | int) and not isinstance(value, bool):
            return value
    nested = (cart_id(v) for k, v in result.items() if isinstance(v, Mapping) and re.match(r"(?i)cart|session", str(k)))
    return next((v for v in nested if v is not None), None)


def session(run: Run, ctx: Context) -> Result:
    """In rpc mode: add two different items, then show the cart; it lists both."""
    found = _program_and_tools(run)
    if isinstance(found, Result):
        return found
    program, tools = found
    add = next((t for t in tools if "add" in words(t.name)), None)
    if add is None:
        return unmeasured(f"no add operation: {', '.join(t.name for t in tools)}")
    show = show_tool(tools, add)
    key = item_key(add)
    if show is None or key is None:
        what = "no show operation" if show is None else f"{add.signature()} has no string argument naming the item"
        return unmeasured(f"{what}: {', '.join(t.name for t in tools)}")
    with LineRpc(program.command(["rpc"])) as rpc:
        return _Session(rpc, tools, add, show).run(key)


@dataclass(frozen=True, slots=True)
class _Session:
    rpc: LineRpc
    tools: Sequence[Tool]
    add: Tool
    show: Tool

    def run(self, key: str) -> Result:
        base = _object(sample(self.add.input_schema))
        id_key = next((k for k in self.add.properties() if ID_KEY.match(k)), None)
        if id_key and id_key not in self.add.required():
            base.pop(id_key, None)
        elif id_key:
            base[id_key] = self._created(base.get(id_key))
        first = self.rpc.call(self.add.name, {**base, key: ITEMS[0]})
        if not has_result(first):
            return failed(f"{self.add.name} {ITEMS[0]} → {describe(first)}; {self.rpc.state()}")
        cart = base.get(id_key) if id_key else None
        cart = cart_id((first or {}).get("result")) or cart
        ids = {id_key: cart} if id_key and cart is not None else {}
        second = self.rpc.call(self.add.name, {**base, key: ITEMS[1], **ids})
        if not has_result(second):
            return failed(f"{self.add.name} {ITEMS[1]} after {ITEMS[0]} → {describe(second)}; {self.rpc.state()}")
        show_args = _object(sample(self.show.input_schema))
        show_id = next((k for k in self.show.properties() if ID_KEY.match(k)), None)
        if show_id and cart is not None:
            show_args[show_id] = cart
        shown = self.rpc.call(self.show.name, show_args)
        body = json.dumps((shown or {}).get("result"))
        missing = [i for i in ITEMS if i not in body] if has_result(shown) else list(ITEMS)
        if missing:
            return failed(
                f"{self.show.name} after adding {' and '.join(ITEMS)} → {describe(shown)}: no {', '.join(missing)}"
            )
        via = f" (cart {cart})" if cart is not None and (ids or show_id) else ""
        return passed(f"{self.add.name} {ITEMS[0]}, {ITEMS[1]}{via}; {self.show.name} lists both")

    def _created(self, sampled_id: Json) -> Json:
        """A required cart id: from a create operation's result when there is one, else the sample."""
        create = next((t for t in self.tools if CREATE_WORDS & set(words(t.name))), None)
        if create is None:
            return sampled_id
        made = self.rpc.call(create.name, _object(sample(create.input_schema)))
        found = cart_id((made or {}).get("result"))
        return found if found is not None else sampled_id


def _file_arguments(tool: Tool) -> Reprice | None:
    strings = tool.string_properties()
    output = next((p for p in strings if OUTPUT_WORDS & set(words(p))), None)
    source = next((p for p in strings if p != output and SOURCE_WORDS & set(words(p))), None)
    return Reprice(tool, source, output) if source and output else None


def _program_and_tools(run: Run) -> tuple[Program, list[Tool]] | Result:
    found = run.program
    if isinstance(found, str):
        return unmeasured(found)
    tools = run.tools
    if isinstance(tools, str):
        return unmeasured(f"no tool definitions: {tools}")
    return found, tools


def _export(ctx: Context, spec: tuple[str, int]) -> Path:
    name, count = spec
    return ctx.cached(name, lambda path: _write_carts(path, count))


def _write_carts(path: Path, count: int) -> None:
    with path.open("w") as out:
        for start in range(0, count, 100_000):
            out.write("".join(CART.format(i=i) for i in range(start, min(count, start + 100_000))))


def _call_for(tools: Sequence[Tool], run: Run, ctx: Context) -> MakeCall:
    """The re-pricing operation on a small export when there is one, else a likely call."""
    reprice = find_reprice(tools)
    if isinstance(reprice, Reprice):
        return reprice.maker(_export(ctx, SMALL_EXPORT), ctx.scratch(run.id))
    return pick_call(tools)


def _with_program(probe: Callable[[Program], Result]) -> Check:
    def check(run: Run, _ctx: Context) -> Result:
        found = run.program
        return unmeasured(found) if isinstance(found, str) else probe(found)

    return check


def _rpc(run: Run, ctx: Context) -> Result:
    found = run.program
    if isinstance(found, str):
        return unmeasured(found)
    tools = run.tools
    return probes.rpc_mode(found, None if isinstance(tools, str) else _call_for(tools, run, ctx))


def _mcp(run: Run, ctx: Context) -> Result:
    found = run.program
    if isinstance(found, str):
        return unmeasured(found)
    return probes.mcp_mode(found, lambda tools: _call_for(tools, run, ctx))


def _slow(probe: Callable[[Program, Reprice, Context, Path], Result]) -> Check:
    """A check of the re-pricing operation on the big export."""

    def check(run: Run, ctx: Context) -> Result:
        found = _program_and_tools(run)
        if isinstance(found, Result):
            return found
        reprice = find_reprice(found[1])
        if isinstance(reprice, str):
            return unmeasured(reprice)
        return probe(found[0], reprice, ctx, ctx.scratch(run.id))

    return check


def _finishes(program: Program, reprice: Reprice, ctx: Context, scratch: Path) -> Result:
    return probes.finishes(program, reprice.maker(_export(ctx, BIG_EXPORT), scratch), FINISH_TIMEOUT)


def _progress_rpc(program: Program, reprice: Reprice, ctx: Context, scratch: Path) -> Result:
    return longops.progress_rpc(program, reprice.maker(_export(ctx, BIG_EXPORT), scratch))


def _progress_mcp(program: Program, reprice: Reprice, ctx: Context, scratch: Path) -> Result:
    return longops.progress_mcp(program, reprice.maker(_export(ctx, BIG_EXPORT), scratch))


def _cancel_rpc(program: Program, reprice: Reprice, ctx: Context, scratch: Path) -> Result:
    later = reprice.call(scratch / "missing-export.jsonl", scratch / "later.jsonl")
    return longops.cancel_rpc(program, reprice.maker(_export(ctx, BIG_EXPORT), scratch), later)


def _cancel_mcp(program: Program, reprice: Reprice, ctx: Context, scratch: Path) -> Result:
    return longops.cancel_mcp(program, reprice.maker(_export(ctx, BIG_EXPORT), scratch))


def _object(value: Json) -> dict[str, Json]:
    return value if isinstance(value, dict) else {}


CHECKS: Mapping[str, Check] = MappingProxyType(
    {
        "read-before-edit": lambda run, ctx: journal.read_before_edit(run.calls, ctx.guide),
        "no-read": lambda run, ctx: journal.no_read(run.calls, ctx.guide),
        "named": _with_program(clicheck.named),
        "help": _with_program(clicheck.help_text),
        "version": _with_program(clicheck.version),
        "help-json": lambda run, _ctx: (
            unmeasured(run.program) if isinstance(run.program, str) else clicheck.help_json(run.tools)
        ),
        "bad-flag": _with_program(clicheck.bad_flag),
        "cli-input": lambda run, _ctx: (
            unmeasured(run.program) if isinstance(run.program, str) else clicheck.cli_input(run.program, run.tools)
        ),
        "rpc": _rpc,
        "mcp": _mcp,
        "session": session,
        "finishes": _slow(_finishes),
        "progress-rpc": _slow(_progress_rpc),
        "progress-mcp": _slow(_progress_mcp),
        "cancel-rpc": _slow(_cancel_rpc),
        "cancel-mcp": _slow(_cancel_mcp),
    }
)
