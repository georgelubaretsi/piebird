"""An MCP client over a program's stdio, on LineRpc.

It speaks the current spec first: no handshake, the protocol version and client capabilities in
every request's `_meta`. A server that doesn't answer `tools/list` that way is started again
and gets the `initialize` handshake of earlier versions.
"""

import json
from typing import Self

from analysis.program import Command
from analysis.rpcio import LineRpc, Message, RequestId, describe
from analysis.tools import Call, Tool, parse_tools

PER_REQUEST_META: dict[str, object] = {
    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
    "io.modelcontextprotocol/clientCapabilities": {},
}
HANDSHAKE_VERSION = "2025-11-25"
PER_REQUEST = "per-request _meta"
HANDSHAKE = "initialize handshake"


class McpClient:
    def __init__(self, command: Command) -> None:
        self._command = command
        self.style = PER_REQUEST
        self.rpc = LineRpc(command)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def open(self, timeout: float = 20.0) -> list[Tool] | str:
        """The server's tools, or a string saying what each style got."""
        reply = self.request("tools/list", {}, timeout=timeout)
        tools = _tools(reply)
        if not isinstance(tools, str):
            return tools
        first = f"tools/list with {PER_REQUEST}: {tools}, {self.rpc.state()}"
        self.rpc.close()
        self.style = HANDSHAKE
        self.rpc = LineRpc(self._command)
        init = self.request(
            "initialize",
            {"protocolVersion": HANDSHAKE_VERSION, "capabilities": {}, "clientInfo": {"name": "bench", "version": "0"}},
            timeout=timeout,
        )
        if init is None or "result" not in init:
            return f"{first}; initialize: {describe(init)}, {self.rpc.state()}"
        self.notify("notifications/initialized", {})
        listed = _tools(self.request("tools/list", {}, timeout=timeout))
        return f"{first}; tools/list after initialize: {listed}" if isinstance(listed, str) else listed

    def params(self, params: dict[str, object], meta: dict[str, object] | None = None) -> dict[str, object]:
        merged = {**PER_REQUEST_META, **(meta or {})} if self.style == PER_REQUEST else meta
        return {**params, "_meta": merged} if merged else params

    def request(self, method: str, params: dict[str, object], timeout: float = 30.0) -> Message | None:
        return self.rpc.call(method, self.params(params), timeout)

    def notify(self, method: str, params: dict[str, object]) -> None:
        self.rpc.notify(method, self.params(params))

    def send_call(self, call: Call, progress_token: str | None = None) -> RequestId:
        meta: dict[str, object] = {"progressToken": progress_token} if progress_token else {}
        params = self.params({"name": call.tool, "arguments": call.args}, meta)
        return self.rpc.send("tools/call", params)

    def call_tool(self, call: Call, timeout: float = 30.0) -> Message | None:
        return self.rpc.wait(self.send_call(call), timeout)

    def cancel(self, request_id: RequestId, reason: str = "bench probe") -> None:
        self.notify("notifications/cancelled", {"requestId": request_id, "reason": reason})

    def close(self) -> None:
        self.rpc.close()


def tool_outcome(reply: Message | None) -> tuple[bool, str]:
    """Whether a tools/call reply is a result without `isError`, and what it said."""
    result = reply.get("result") if reply else None
    if not isinstance(result, dict):
        return False, describe(reply)
    shown = result.get("structuredContent", result.get("content"))
    text = " ".join(json.dumps(shown).split())
    text = text if len(text) <= 160 else text[:159] + "…"
    if result.get("isError") is True:
        return False, f"isError: {text}"
    return True, f"result: {text}"


def _tools(reply: Message | None) -> list[Tool] | str:
    result = reply.get("result") if reply else None
    if not isinstance(result, dict):
        return describe(reply)
    return parse_tools(result)
