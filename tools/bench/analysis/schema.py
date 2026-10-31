"""One valid instance of a JSON Schema, small and plausible, for probing a tool (pure).

Covers what tool schemas use: types (a type list or union prefers numbers, so a price typed
`["string", "number"]` gets a number), `const`, `enum`, `default`, `examples`, required
properties, nested objects and arrays, numeric bounds and `multipleOf`, string lengths,
common formats, `pattern` (best effort, see regexgen), `allOf`/`anyOf`/`oneOf` and local `$ref`.
Not covered: `not`, `if`/`then`/`else`, `contains`, `dependentSchemas`, remote refs.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from analysis import regexgen

type Json = bool | int | float | str | list[Json] | dict[str, Json] | None
type Schema = Mapping[str, object]

MAX_DEPTH = 24
# Lower sorts first: a value of an earlier type is tried before a later one.
TYPE_RANK = {"integer": 0, "number": 1, "boolean": 2, "string": 3, "array": 4, "object": 5, "null": 6}
FORMATS = {
    "date-time": "2026-01-01T00:00:00Z",
    "date": "2026-01-01",
    "time": "00:00:00Z",
    "duration": "P1D",
    "email": "probe@example.com",
    "idn-email": "probe@example.com",
    "hostname": "example.com",
    "idn-hostname": "example.com",
    "ipv4": "127.0.0.1",
    "ipv6": "::1",
    "uri": "https://example.com/",
    "uri-reference": "https://example.com/",
    "iri": "https://example.com/",
    "url": "https://example.com/",
    "uuid": "00000000-0000-4000-8000-000000000001",
    "regex": ".*",
    "json-pointer": "/a",
}
# Plausible strings for the patterns tool schemas use (prices, lines like `12x2`, ids).
CANDIDATES = ("1", "1:1", "1x1", "12.50:2", "12x2", "1.00", "a", "x", "abc", "a:b", "sku-1")


@dataclass(frozen=True, slots=True)
class _At:
    root: object
    depth: int

    def deeper(self) -> _At:
        return _At(self.root, self.depth + 1)


def sample(schema: object) -> Json:
    """A value `schema` accepts (best effort; `None` for `true` and `{}`)."""
    return _sample(schema, _At(schema, 0))


def _sample(schema: object, at: _At) -> Json:
    if not isinstance(schema, Mapping) or at.depth > MAX_DEPTH:
        return None
    s = _resolve(schema, at)
    picked = _given(s)
    if picked is not None:
        return picked[0]
    all_of = s.get("allOf")
    if isinstance(all_of, list) and all_of:
        merged = _merge([{k: v for k, v in s.items() if k != "allOf"}, *(_resolve(x, at) for x in all_of)])
        return _sample(merged, at.deeper())
    for key in ("anyOf", "oneOf"):
        options = s.get(key)
        if isinstance(options, list) and options:
            rest = {k: v for k, v in s.items() if k != key}
            option = min(options, key=lambda o: _rank(_resolve(o, at)))
            return _sample(_merge([rest, _resolve(option, at)]), at.deeper())
    return _typed(s, _type_of(s), at)


def _given(s: Schema) -> tuple[Json] | None:
    """The value the schema names itself: const, enum (its default if listed), default, example."""
    if "const" in s:
        return (_json(s["const"]),)
    enum = s.get("enum")
    if isinstance(enum, list) and enum:
        default = s.get("default")
        listed = any(default == v and type(default) is type(v) for v in enum)
        return (_json(default if listed else enum[0]),)
    if "default" in s:
        return (_json(s["default"]),)
    examples = s.get("examples")
    if isinstance(examples, list) and examples:
        return (_json(examples[0]),)
    return None


def _typed(s: Schema, kind: str | None, at: _At) -> Json:
    match kind:
        case "object":
            return _object(s, at)
        case "array":
            return _array(s, at)
        case "integer" | "number":
            return _number(s, integer=kind == "integer")
        case "string":
            return _string(s)
        case "boolean":
            return False
        case _:
            return None


def _type_of(s: Schema) -> str | None:
    kind = s.get("type")
    if isinstance(kind, str):
        return kind
    if isinstance(kind, list):
        names = [k for k in kind if isinstance(k, str)]
        return min(names, key=lambda k: TYPE_RANK.get(k, 9)) if names else None
    if "properties" in s or "required" in s:
        return "object"
    if "items" in s or "prefixItems" in s:
        return "array"
    if any(k in s for k in ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf")):
        return "number"
    if any(k in s for k in ("minLength", "maxLength", "pattern", "format")):
        return "string"
    return None


def _rank(s: Schema) -> int:
    kind = _type_of(s)
    return TYPE_RANK.get(kind, 3) if kind else 3


def _object(s: Schema, at: _At) -> dict[str, Json]:
    props = s.get("properties")
    props = props if isinstance(props, Mapping) else {}
    required = s.get("required")
    keys = [k for k in required if isinstance(k, str)] if isinstance(required, list) else []
    least = s.get("minProperties")
    if isinstance(least, int) and least > len(keys):
        keys += [k for k in props if k not in keys][: least - len(keys)]
    extra = s.get("additionalProperties")
    return {k: _sample(props.get(k, extra if isinstance(extra, Mapping) else {}), at.deeper()) for k in keys}


def _array(s: Schema, at: _At) -> list[Json]:
    items = s.get("items")
    prefix = s.get("prefixItems")
    tuple_items = prefix if isinstance(prefix, list) else items if isinstance(items, list) else []
    rest = items if isinstance(items, Mapping) else s.get("additionalItems")
    least = _int(s.get("minItems"), 0)
    most = _int(s.get("maxItems"), MAX_DEPTH)
    count = min(max(least, len(tuple_items), 1 if isinstance(rest, Mapping) else 0), most)
    out = [_sample(x, at.deeper()) for x in tuple_items[:count]]
    value = _sample(rest, at.deeper()) if isinstance(rest, Mapping) else 1
    unique = bool(s.get("uniqueItems")) or not isinstance(rest, Mapping)
    out += [_vary(value, i) if unique else value for i in range(len(out), count)]
    return out


@dataclass(frozen=True, slots=True)
class _Bounds:
    low: Decimal | None
    low_open: bool
    high: Decimal | None
    high_open: bool

    def below(self, value: Decimal) -> bool:
        return self.low is not None and (value < self.low or (self.low_open and value <= self.low))

    def above(self, value: Decimal) -> bool:
        return self.high is not None and (value > self.high or (self.high_open and value >= self.high))


def _number(s: Schema, *, integer: bool) -> int | float:
    """1 when allowed; else the nearest allowed value on the step, inside the bounds."""
    bounds = _Bounds(*_bound(s, "minimum", "exclusiveMinimum"), *_bound(s, "maximum", "exclusiveMaximum"))
    unit = _unit(s.get("multipleOf"), integer=integer)
    value = Decimal(1)
    if bounds.below(value) and bounds.low is not None:
        value = bounds.low + (unit or Decimal(1)) if bounds.low_open else bounds.low
    if bounds.above(value) and bounds.high is not None:
        value = bounds.high - (unit or Decimal(1)) if bounds.high_open else bounds.high
        if bounds.below(value) and bounds.low is not None:
            value = (bounds.low + bounds.high) / 2
    if unit is not None:
        value = math.ceil(value / unit) * unit
        if bounds.above(value) and bounds.high is not None:
            value = math.floor(bounds.high / unit) * unit
    return int(value) if value == value.to_integral_value() else float(value)


def _unit(step: object, *, integer: bool) -> Decimal | None:
    """The step values move by: `multipleOf`, made whole for integers (0.5 → 1, 0.3 → 3)."""
    unit = _decimal(step)
    if unit is not None and unit <= 0:
        unit = None
    if not integer:
        return unit
    if unit is None:
        return Decimal(1)
    whole = next((unit * n for n in range(1, 1001) if unit * n == (unit * n).to_integral_value()), None)
    return whole or unit


def _bound(s: Schema, inclusive: str, exclusive: str) -> tuple[Decimal | None, bool]:
    """A bound and whether it is open; draft 4's boolean `exclusiveMinimum` included."""
    closed = _decimal(s.get(inclusive))
    opened = s.get(exclusive)
    if isinstance(opened, bool):
        return closed, opened and closed is not None
    open_value = _decimal(opened)
    if open_value is not None and (closed is None or _tighter(open_value, closed, inclusive)):
        return open_value, True
    return closed, False


def _tighter(open_value: Decimal, closed: Decimal, inclusive: str) -> bool:
    return open_value >= closed if inclusive == "minimum" else open_value <= closed


def _string(s: Schema) -> str:
    least = _int(s.get("minLength"), 0)
    most = _int(s.get("maxLength"), 10_000)
    pattern = s.get("pattern")
    fmt = s.get("format")
    tries = [FORMATS[fmt]] if isinstance(fmt, str) and fmt in FORMATS else []
    tries += CANDIDATES
    if isinstance(pattern, str):
        generated = regexgen.generate(pattern)
        tries += [generated] if generated is not None else []
        tries = [t for t in tries if regexgen.matches(pattern, t)] or tries
    fits = [t for t in tries if least <= len(t) <= most]
    if fits:
        return fits[0]
    value = tries[0] or "a"
    return (value + value[-1] * least)[: max(least, min(most, len(value)))]


def _resolve(schema: object, at: _At) -> Schema:
    """A local `$ref` replaced by its target (siblings win); anything else unchanged."""
    if not isinstance(schema, Mapping):
        return {}
    ref = schema.get("$ref")
    if not isinstance(ref, str) or not ref.startswith("#") or at.depth > MAX_DEPTH:
        return schema
    target: object = at.root
    for part in [p for p in ref[1:].split("/") if p]:
        key = part.replace("~1", "/").replace("~0", "~")
        target = target.get(key) if isinstance(target, Mapping) else None
    rest = {k: v for k, v in schema.items() if k != "$ref"}
    return {**_resolve(target, at.deeper()), **rest}


def _merge(parts: Sequence[Schema]) -> Schema:
    """allOf: properties and required lists joined, other keys from the last part that has them."""
    merged: dict[str, object] = {}
    props: dict[str, object] = {}
    required: list[object] = []
    for part in parts:
        merged.update(part)
        p = part.get("properties")
        props.update(p if isinstance(p, Mapping) else {})
        r = part.get("required")
        required += [k for k in r if k not in required] if isinstance(r, list) else []
    if props:
        merged["properties"] = props
    if required:
        merged["required"] = required
    return merged


def _vary(value: Json, i: int) -> Json:
    """Distinct items for `uniqueItems` (scalars only; objects repeat)."""
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int | float):
        return value + i
    return f"{value}{i}" if isinstance(value, str) else value


def _json(value: object) -> Json:
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, list):
        return [_json(v) for v in value]
    if isinstance(value, Mapping):
        return {str(k): _json(v) for k, v in value.items()}
    return str(value)


def _int(value: object, fallback: int) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else fallback


def _decimal(value: object) -> Decimal | None:
    """A JSON number as an exact decimal (`0.1` stays 0.1); anything else None."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return Decimal(str(value)) if math.isfinite(value) else None
