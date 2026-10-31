"""MCP tool definitions as programs print them, and the calls probes make with them (pure)."""

import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

from analysis.schema import Json, Schema, sample


@dataclass(frozen=True, slots=True)
class Tool:
    name: str
    input_schema: Schema
    description: str = ""
    read_only: bool | None = None  # annotations.readOnlyHint

    def properties(self) -> Mapping[str, Schema]:
        props = self.input_schema.get("properties")
        if not isinstance(props, Mapping):
            return {}
        return {k: v for k, v in props.items() if isinstance(k, str) and isinstance(v, Mapping)}

    def required(self) -> list[str]:
        req = self.input_schema.get("required")
        return [k for k in req if isinstance(k, str)] if isinstance(req, list) else []

    def string_properties(self) -> list[str]:
        return [k for k, v in self.properties().items() if _allows_string(v)]

    def rejects_bogus(self) -> bool:
        """Whether `{"bogus": 1}` breaks the schema: a required field, or no extra fields allowed."""
        return bool(self.required()) or self.input_schema.get("additionalProperties") is False

    def signature(self) -> str:
        return f"{self.name}({', '.join(self.properties())})"


@dataclass(frozen=True, slots=True)
class Call:
    tool: str
    args: dict[str, Json] = field(default_factory=dict)

    def show(self) -> str:
        return f"{self.tool} {json.dumps(self.args)}"


# Makes a fresh call per use; the tag names it (output files differ per call).
type MakeCall = Callable[[str], Call]


def parse_tools(value: object) -> list[Tool] | str:
    """`{"tools": [...]}` or a bare list of definitions; a string says what was wrong."""
    items = value.get("tools") if isinstance(value, Mapping) else value
    if not isinstance(items, list):
        shape = (
            f"an object with keys {', '.join(map(str, value))}" if isinstance(value, Mapping) else type(value).__name__
        )
        return f"not a list of tool definitions: {shape}"
    if not items:
        return "an empty tool list"
    tools: list[Tool] = []
    for i, item in enumerate(items, start=1):
        if not isinstance(item, Mapping) or not isinstance(item.get("name"), str):
            return f"tool {i} has no name"
        schema = item.get("inputSchema")
        if not isinstance(schema, Mapping):
            return f"tool {item['name']} has no inputSchema object"
        annotations = item.get("annotations")
        hint = annotations.get("readOnlyHint") if isinstance(annotations, Mapping) else None
        description = item.get("description")
        tools.append(
            Tool(
                name=item["name"],
                input_schema=schema,
                description=description if isinstance(description, str) else "",
                read_only=hint if isinstance(hint, bool) else None,
            )
        )
    return tools


def words(name: str) -> list[str]:
    """`applyGiftCard`, `apply_gift_card`, `apply-gift-card` → apply, gift, card."""
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    return [w.lower() for w in re.split(r"[^A-Za-z0-9]+", spaced) if w]


def sampled(tool: Tool) -> MakeCall:
    return lambda _tag: Call(tool.name, _object(sample(tool.input_schema)))


def pick_call(tools: Sequence[Tool]) -> MakeCall:
    """A call likely to succeed: a read-only tool if one says so, else the one needing least input."""
    read_only = [t for t in tools if t.read_only]
    pool = read_only or list(tools)
    return sampled(min(pool, key=lambda t: len(t.required())))


def _allows_string(schema: Schema) -> bool:
    kind = schema.get("type")
    return kind == "string" or (isinstance(kind, list) and "string" in kind)


def _object(value: Json) -> dict[str, Json]:
    return value if isinstance(value, dict) else {}
