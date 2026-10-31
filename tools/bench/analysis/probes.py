"""Probes of a program's long-lived modes: `<program> rpc` (JSON-RPC 2.0, one message per line)
and `<program> mcp` (MCP over stdio). The caller picks the operation and its input; the probes
judge the protocol. Progress and cancellation probes are in `longops`.
"""

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from analysis.mcp import McpClient, tool_outcome
from analysis.program import Program
from analysis.result import Result, failed, passed, unmeasured
from analysis.rpcio import LineRpc, describe, error_of, has_result
from analysis.tools import MakeCall, Tool

PARSE_ERROR = -32700
MALFORMED = "{not json"


@dataclass(frozen=True, slots=True)
class Timing:
    """Seconds each probe waits; tests shorten them."""

    reply: float = 30.0  # a call's reply
    open: float = 20.0  # MCP's tools/list or initialize reply
    progress: float = 60.0  # the first notifications/progress
    start: float = 5.0  # a long call's head start before it is cancelled
    stop: float = 10.0  # after the cancel, for a reply to the cancelled call
    grace: float = 1.0  # progress later than this after the cancel means the work went on


DEFAULT = Timing()
# Picks the call for the MCP probe from the server's own tool list; a string says why none.
type Pick = Callable[[Sequence[Tool]], MakeCall | str]


def rpc_mode(program: Program, make: MakeCall | None, timing: Timing = DEFAULT) -> Result:
    """A malformed line gets -32700 and the loop goes on; a valid call returns a result, with
    `params._meta` too."""
    with LineRpc(program.command(["rpc"])) as rpc:
        rpc.send_raw(MALFORMED)
        parse = rpc.wait(None, timing.reply)
        code = (error_of(parse) or {}).get("code")
        if code != PARSE_ERROR:
            return failed(f"malformed line → {describe(parse)}, not error {PARSE_ERROR}; {rpc.state()}")
        if make is None:
            return unmeasured("malformed line → -32700, but no tool definitions to make a call with")
        call = make("rpc")
        first = rpc.call(call.tool, call.args, timing.reply)
        if not has_result(first):
            return failed(f"after the malformed line, {call.show()} → {describe(first)}; {rpc.state()}")
        again = make("rpc-meta")
        second = rpc.call(again.tool, {**again.args, "_meta": {"progressToken": "bench-meta"}}, timing.reply)
        if not has_result(second):
            return failed(f"{again.tool} with params._meta → {describe(second)} (without it: a result)")
        return passed(f"malformed line → -32700; {call.tool} → result, with params._meta too")


def mcp_mode(program: Program, pick: Pick, timing: Timing = DEFAULT) -> Result:
    """tools/list lists tools and a call of one returns a result without `isError`."""
    with McpClient(program.command(["mcp"])) as client:
        tools = client.open(timing.open)
        if isinstance(tools, str):
            return failed(f"no tool list: {tools}")
        make = pick(tools)
        if isinstance(make, str):
            return unmeasured(f"{len(tools)} tools ({client.style}), but {make}")
        call = make("mcp")
        ok, said = tool_outcome(client.call_tool(call, timing.reply))
        listed = f"{client.style}, {len(tools)} tools"
        if not ok:
            return failed(f"{listed}; {call.show()} → {said}; {client.rpc.state()}")
        return passed(f"{listed}; {call.tool} → {said}")


def finishes(program: Program, make: MakeCall, timeout: float) -> Result:
    """An rpc call returns a result within `timeout` seconds of starting the program."""
    start = time.monotonic()
    with LineRpc(program.command(["rpc"])) as rpc:
        call = make("finishes")
        reply = rpc.call(call.tool, call.args, timeout)
        took = f"{time.monotonic() - start:.0f} s"
        if has_result(reply):
            return passed(f"result in {took}: {describe(reply)}")
        if reply is not None:
            return failed(f"{call.show()} → {describe(reply)} after {took}")
        return failed(f"no result in {took} for {call.show()}; {rpc.state()}")
