"""Probes of long operations in both modes: `notifications/progress` for the request's
`progressToken`, and stopping on `notifications/cancelled`.

A call stops when it gets an error reply (rpc) or no reply (MCP, as its spec asks) and sends no
progress more than `grace` seconds after the cancel. A program that sends no progress at all and
keeps working silently, without replying, can't be told apart from one that stopped: the later
call shows only that it still answers.
"""

import json
import time
from collections import Counter
from dataclasses import dataclass

from analysis.mcp import McpClient
from analysis.probes import DEFAULT, Timing
from analysis.program import Program
from analysis.result import Result, failed, passed, unmeasured
from analysis.rpcio import LineRpc, Message, Received, RequestId, describe, has_result, is_reply
from analysis.schema import Json
from analysis.tools import Call, MakeCall

PROGRESS = "notifications/progress"
CANCELLED = "notifications/cancelled"
PROGRESS_TOKEN = "bench-progress"
CANCEL_TOKEN = "bench-cancel"


def progress_rpc(program: Program, make: MakeCall, timing: Timing = DEFAULT) -> Result:
    with LineRpc(program.command(["rpc"])) as rpc:
        call = make("progress")
        sent = rpc.send(call.tool, _with_token(call.args, PROGRESS_TOKEN))
        return _progress(rpc, sent, timing)


def progress_mcp(program: Program, make: MakeCall, timing: Timing = DEFAULT) -> Result:
    with McpClient(program.command(["mcp"])) as client:
        tools = client.open(timing.open)
        if isinstance(tools, str):
            return unmeasured(f"mcp mode lists no tools: {tools}")
        sent = client.send_call(make("progress"), PROGRESS_TOKEN)
        return _progress(client.rpc, sent, timing)


def cancel_rpc(program: Program, make: MakeCall, later: Call, timing: Timing = DEFAULT) -> Result:
    """After the cancel the call stops (error reply, or no reply and no more progress) and the
    program answers `later`."""
    with LineRpc(program.command(["rpc"])) as rpc:
        call = make("cancelled")
        sent = rpc.send(call.tool, _with_token(call.args, CANCEL_TOKEN))
        early = _head_start(rpc, sent, timing)
        if early is not None:
            return early
        cancel = _Cancel(rpc, sent, time.monotonic())
        rpc.notify(CANCELLED, {"requestId": sent, "reason": "bench probe"})
        stopped = _rpc_stopped(cancel, timing)
        if isinstance(stopped, Result):
            return stopped
        answer = rpc.call(later.tool, later.args, timing.reply)
        if answer is None:
            return failed(f"{stopped}, but no reply to a later call in {timing.reply:.0f} s; {rpc.state()}")
        return passed(f"{stopped}; a later call got {describe(answer)}")


def cancel_mcp(program: Program, make: MakeCall, timing: Timing = DEFAULT) -> Result:
    """No reply to the cancelled call, no more progress, and the server still answers."""
    with McpClient(program.command(["mcp"])) as client:
        tools = client.open(timing.open)
        if isinstance(tools, str):
            return unmeasured(f"mcp mode lists no tools: {tools}")
        sent = client.send_call(make("cancelled"), CANCEL_TOKEN)
        early = _head_start(client.rpc, sent, timing)
        if early is not None:
            return early
        cancel = _Cancel(client.rpc, sent, time.monotonic())
        client.cancel(sent)
        reply = cancel.reply(timing.stop)
        if reply is not None:
            return failed(
                f"replied to the cancelled call {reply.at - cancel.at:.1f} s after the cancel: {describe(reply.message)}"
            )
        late = cancel.late_progress(timing.grace)
        if late:
            return failed(
                f"no reply, but {late} notifications/progress more than {timing.grace:.0f} s after the cancel"
            )
        listed = client.request("tools/list", {}, timing.reply)
        if not has_result(listed):
            return failed(f"no reply to the cancelled call, then tools/list → {describe(listed)}; {client.rpc.state()}")
        return passed(f"no reply in {timing.stop:.0f} s after the cancel, no progress after it; tools/list answered")


@dataclass(frozen=True, slots=True)
class _Cancel:
    rpc: LineRpc
    sent: RequestId
    at: float  # when the cancel was sent

    def reply(self, timeout: float) -> Received | None:
        return self.rpc.wait_for(lambda r: is_reply(r.message, self.sent), timeout, take=True)

    def late_progress(self, grace: float) -> int:
        notes = self.rpc.notes
        return sum(1 for r in notes if r.at >= self.at + grace and _token(r.message) == CANCEL_TOKEN)


def _progress(rpc: LineRpc, sent: RequestId, timing: Timing) -> Result:
    start = time.monotonic()
    first = rpc.wait_for(lambda r: _is_progress(r.message) or is_reply(r.message, sent), timing.progress)
    took = time.monotonic() - start
    if first is None:
        return failed(f"no notifications/progress or reply in {took:.0f} s; {_methods(rpc)}; {rpc.state()}")
    if not _is_progress(first.message):
        return failed(
            f"reply after {took:.1f} s with no notifications/progress: {describe(first.message)}; {_methods(rpc)}"
        )
    token = _token(first.message)
    if token != PROGRESS_TOKEN:
        return failed(f"notifications/progress with progressToken {token!r}, not {PROGRESS_TOKEN!r}")
    params = " ".join(json.dumps(first.message.get("params")).split())[:120]
    return passed(f"notifications/progress after {took:.1f} s: {params}")


def _head_start(rpc: LineRpc, sent: RequestId, timing: Timing) -> Result | None:
    """Lets the call get going (its first progress, or `timing.start`); a result if it can't be cancelled."""
    start = time.monotonic()
    first = rpc.wait_for(lambda r: _token(r.message) == CANCEL_TOKEN or is_reply(r.message, sent), timing.start)
    if first is not None and is_reply(first.message, sent):
        took = first.at - start
        return unmeasured(f"the call replied {took:.1f} s in, before it could be cancelled: {describe(first.message)}")
    if not rpc.alive():
        return failed(f"before the cancel: {rpc.state()}")
    return None


def _rpc_stopped(cancel: _Cancel, timing: Timing) -> Result | str:
    """How the call stopped, or the failure showing it didn't."""
    reply = cancel.reply(timing.stop)
    if reply is not None and has_result(reply.message):
        return failed(
            f"the cancelled call returned {describe(reply.message)} {reply.at - cancel.at:.1f} s after the cancel"
        )
    if reply is not None:
        time.sleep(timing.grace * 2)  # time for progress that goes on
    late = cancel.late_progress(timing.grace)
    seen = f"{describe(reply.message)} {reply.at - cancel.at:.1f} s after the cancel" if reply else "no reply"
    if late:
        return failed(f"{seen}, but {late} notifications/progress more than {timing.grace:.0f} s after it")
    if reply is None and not cancel.rpc.alive():
        return failed(f"no reply to the cancelled call; {cancel.rpc.state()}")
    return seen if reply else f"no reply and no progress in {timing.stop:.0f} s after the cancel"


def _with_token(args: dict[str, Json], token: str) -> dict[str, Json]:
    return {**args, "_meta": {"progressToken": token}}


def _is_progress(message: Message) -> bool:
    return message.get("method") == PROGRESS


def _token(message: Message) -> object:
    params = message.get("params")
    return params.get("progressToken") if _is_progress(message) and isinstance(params, dict) else None


def _methods(rpc: LineRpc) -> str:
    counts = Counter(str(r.message.get("method")) for r in rpc.notes)
    if not counts:
        return "no notifications"
    return "notifications seen: " + ", ".join(f"{m} x{n}" for m, n in counts.most_common(4))
