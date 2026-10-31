"""A fake cart program keeping the interfaces contract, for the probes' tests: CLI, rpc and mcp.

FAKE_BAD=1 breaks every part of the contract the probes check but cancelling. FAKE_CANCEL=ignore
keeps working after a cancel; FAKE_CANCEL=reply answers a cancelled MCP call. FAKE_MCP=handshake
makes mcp mode refuse requests before `initialize`. FAKE_DELAY: seconds re-pricing takes per cart.
FAKE_FORGET=1 makes `show` forget what was added. FAKE_CARTS=1 keeps carts by id: `add_line` makes
one (or takes `cartId`) and returns its id; `show` needs it. FAKE_HELP_JSON_EXIT=<n> makes
`--help --json` print valid definitions, then exit n.
"""

import json
import os
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

type Obj = dict[str, object]

BAD = os.environ.get("FAKE_BAD") == "1"
DELAY = float(os.environ.get("FAKE_DELAY", "0.01"))
CANCEL = os.environ.get("FAKE_CANCEL", "")
FORGET = os.environ.get("FAKE_FORGET") == "1"
HELP_JSON_EXIT = int(os.environ.get("FAKE_HELP_JSON_EXIT", "0"))
CARTS = os.environ.get("FAKE_CARTS") == "1"
CART_ID = {"cartId": {"type": "string"}} if CARTS else {}
LINE = {
    "type": "object",
    "properties": {"price": {"type": "number"}, "qty": {"type": "integer"}},
    "required": ["price", "qty"],
}
TOOLS: list[Obj] = [
    {
        "name": "cart_total",
        "annotations": {"readOnlyHint": True},
        "inputSchema": {
            "type": "object",
            "properties": {"lines": {"type": "array", "items": LINE, "minItems": 1}},
            "required": ["lines"],
            "additionalProperties": False,
        },
    },
    {
        "name": "add_line",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sku": {"type": "string", "minLength": 1},
                "price": {"type": ["string", "number"]},
                **CART_ID,
            },
            "required": ["sku", "price"],
            "additionalProperties": False,
        },
    },
    {
        "name": "show",
        "inputSchema": {
            "type": "object",
            "properties": CART_ID,
            "required": list(CART_ID),
            "additionalProperties": False,
        },
    },
    {
        "name": "reprice",
        "inputSchema": {
            "type": "object",
            "properties": {"carts": {"type": "string"}, "output": {"type": "string"}},
            "required": ["carts", "output"],
            "additionalProperties": False,
        },
    },
]
COMMANDS = {"total": "cart_total", "add": "add_line", "show": "show", "reprice": "reprice"}
HELP = "fake - cart totals\n\nUsage: fake <command> [--json] [--input <file|->]\n\nExample:\n  fake total --input cart.json\n"
BY_ID: dict[str, list[Obj]] = {}
OUT = threading.Lock()
CANCELLED: set[object] = set()
STATE = {"initialized": os.environ.get("FAKE_MCP") != "handshake"}


class InvalidError(Exception):
    pass


@dataclass(frozen=True)
class Request:
    id: object
    token: object  # progressToken, or None


def operate(name: str, args: Obj, request: Request) -> object:
    """An operation's result; InvalidError for bad input, LookupError for an unknown one."""
    tool = next((t for t in TOOLS if t["name"] == name), None)
    if tool is None:
        raise LookupError(name)
    schema = tool["inputSchema"]
    assert isinstance(schema, dict)
    missing = [k for k in schema.get("required", []) if k not in args]
    extra = [k for k in args if k not in schema["properties"]]
    if missing or extra:
        raise InvalidError(f"missing {missing}, unknown {extra}")
    if name == "cart_total":
        lines = args["lines"]
        assert isinstance(lines, list)
        return {"total": sum(line["price"] * line["qty"] for line in lines)}
    if name == "add_line":
        cart_id = str(args.get("cartId") or f"c{len(BY_ID) + 1}") if CARTS else ""
        cart = BY_ID.setdefault(cart_id, [])
        cart.append({"sku": args["sku"], "price": args["price"]})
        return {"cartId": cart_id, "lines": len(cart)} if CARTS else {"lines": len(cart)}
    if name == "show":
        cart = BY_ID.get(str(args.get("cartId", "")), [])
        return {"lines": [] if FORGET else cart}
    return reprice(Path(str(args["carts"])), Path(str(args["output"])), request)


def reprice(source: Path, output: Path, request: Request) -> object:
    try:
        carts = source.read_text().splitlines()
    except OSError as err:
        raise InvalidError(f"can't read {source}") from err
    done = []
    for i, line in enumerate(carts, start=1):
        if request.id in CANCELLED and CANCEL != "ignore":
            raise InterruptedError
        time.sleep(DELAY)
        done.append(json.loads(line)["id"])
        if request.token is not None and not BAD and i % 5 == 0:
            params = {"progressToken": request.token, "progress": i, "total": len(carts)}
            send({"jsonrpc": "2.0", "method": "notifications/progress", "params": params})
    output.write_text("\n".join(done))
    return {"carts": len(done)}


def send(message: Obj) -> None:
    with OUT:
        sys.stdout.write(json.dumps(message) + "\n")
        sys.stdout.flush()


def rpc_reply(method: str, params: Obj, request: Request) -> Obj:
    try:
        return {"jsonrpc": "2.0", "id": request.id, "result": operate(method, params, request)}
    except InvalidError as err:
        return {
            "jsonrpc": "2.0",
            "id": request.id,
            "error": {"code": -32602, "message": str(err), "data": {"code": "invalid_input"}},
        }
    except LookupError:
        return {"jsonrpc": "2.0", "id": request.id, "error": {"code": -32601, "message": "no such method"}}
    except InterruptedError:
        return {"jsonrpc": "2.0", "id": request.id, "error": {"code": -32800, "message": "cancelled"}}


def mcp_reply(method: str, params: Obj, request: Request) -> Obj | None:
    """The reply to an MCP request; None for a cancelled call."""
    reply: Obj = {"jsonrpc": "2.0", "id": request.id}
    if method == "initialize":
        STATE["initialized"] = True
        return reply | {
            "result": {
                "protocolVersion": "2025-11-25",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "fake", "version": "1"},
            }
        }
    if not STATE["initialized"]:
        return reply | {"error": {"code": -32002, "message": "not initialized"}}
    if method == "tools/list":
        return reply | {"result": {"tools": TOOLS}}
    arguments = params.get("arguments")
    try:
        result = operate(str(params.get("name")), arguments if isinstance(arguments, dict) else {}, request)
    except InterruptedError:
        return reply | {"error": {"code": -32800, "message": "cancelled"}} if CANCEL == "reply" else None
    except (InvalidError, LookupError) as err:
        return reply | {"result": {"isError": True, "content": [{"type": "text", "text": str(err)}]}}
    return reply | {"result": {"content": [{"type": "text", "text": json.dumps(result)}], "structuredContent": result}}


def handle(message: Obj, mcp: bool) -> None:
    """Answers one request on its own thread, so cancellations arrive while it works."""
    params = message.get("params")
    params = dict(params) if isinstance(params, dict) else {}
    meta = params.pop("_meta", None)
    request = Request(message.get("id"), meta.get("progressToken") if isinstance(meta, dict) else None)
    method = str(message.get("method"))

    def work() -> None:
        reply = mcp_reply(method, params, request) if mcp else rpc_reply(method, params, request)
        if reply is not None:
            send(reply)

    threading.Thread(target=work, daemon=True).start()


def serve(mcp: bool) -> int:
    if mcp and BAD:
        sys.stderr.write("unknown command: mcp\n")
        return 2
    for raw in sys.stdin:
        try:
            message = json.loads(raw)
        except ValueError:
            if BAD:
                return 1
            send({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}})
            continue
        if message.get("method") == "notifications/cancelled":
            CANCELLED.add((message.get("params") or {}).get("requestId"))
        elif "id" in message:
            handle(message, mcp)
    return 0


def one_shot(words: list[str]) -> int:
    try:
        result = operate(COMMANDS.get(" ".join(words), ""), json.loads(sys.stdin.read() or "{}"), Request(None, None))
    except (InvalidError, LookupError, ValueError) as err:
        if BAD:
            sys.stderr.write(f"oops: {err}\n")
            return 1
        sys.stderr.write(json.dumps({"error": {"code": "invalid_input", "message": str(err)}}) + "\n")
        return 2
    sys.stdout.write(json.dumps(result) + "\n")
    return 0


def cli(args: list[str]) -> int:
    if args == ["--help"]:
        sys.stdout.write("fake - cart totals\n" if BAD else HELP)
        return 0
    if args == ["--help", "--json"]:
        sys.stdout.write(HELP if BAD else json.dumps({"tools": TOOLS}))
        return HELP_JSON_EXIT
    if args == ["--version"]:
        sys.stdout.write("" if BAD else "fake 1.0.0\n")
        return 1 if BAD else 0
    if args and args[0] in ("rpc", "mcp"):
        return serve(args[0] == "mcp")
    words = [a for a in args if not a.startswith("-")]
    if any(a.startswith("--") and a not in ("--json", "--input") for a in args) or not words:
        out, code = (sys.stdout, 0) if BAD else (sys.stderr, 2)
        out.write(f"unknown flag or command: {' '.join(args)}\nRun 'fake --help'.\n")
        return code
    return one_shot(words)


if __name__ == "__main__":
    sys.exit(cli(sys.argv[1:]))
