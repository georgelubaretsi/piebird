from typing import Any

import pytest
from jsonschema import FormatChecker, validators

from analysis import regexgen
from analysis.schema import sample

DRAFT4 = "http://json-schema.org/draft-04/schema#"
DRAFT7 = "http://json-schema.org/draft-07/schema#"
LINE = {
    "type": "object",
    "properties": {"price": {"type": "number", "minimum": 0}, "qty": {"type": "integer", "minimum": 1}},
    "required": ["price", "qty"],
    "additionalProperties": False,
}

# Each sample must validate against its schema (with format checks).
SCHEMAS: list[dict[str, Any]] = [
    {"type": "string"},
    {"type": "string", "minLength": 5, "maxLength": 6},
    {"type": "string", "maxLength": 0},
    {"type": "integer"},
    {"type": "integer", "minimum": 5, "maximum": 9},
    {"type": "integer", "exclusiveMinimum": 0, "maximum": 10000},
    {"type": "integer", "maximum": -3},
    {"type": "integer", "minimum": -9007199254740991, "maximum": 9007199254740991},
    {"type": "integer", "multipleOf": 3},
    {"type": "integer", "multipleOf": 0.5},
    {"type": "number", "minimum": 0, "maximum": 1000000, "multipleOf": 0.01},
    {"type": "number", "exclusiveMinimum": 0.5, "exclusiveMaximum": 0.7},
    {"type": "number", "minimum": 2.5, "multipleOf": 0.25},
    {
        "$schema": DRAFT4,
        "type": "number",
        "minimum": 0,
        "exclusiveMinimum": True,
        "maximum": 1,
        "exclusiveMaximum": True,
    },
    {"type": "boolean"},
    {"type": "null"},
    {"type": ["string", "number"], "description": "Decimal money amount, e.g. 12.50"},
    {"type": ["null", "string"]},
    {"enum": ["fail", "skip"]},
    {"enum": ["fail", "skip"], "default": "skip"},
    {"enum": [0, 1], "default": False},
    {"const": "v1"},
    {"type": "integer", "minimum": 0, "default": 0},
    {"type": "string", "examples": ["12.50"]},
    {"type": "string", "format": "date-time"},
    {"type": "string", "format": "date"},
    {"type": "string", "format": "email"},
    {"type": "string", "format": "uuid"},
    {"type": "string", "format": "ipv4"},
    {"type": "string", "format": "uri"},
    # Patterns from past runs' tool schemas.
    {"type": "string", "minLength": 1, "maxLength": 100, "pattern": r"^\S+$"},
    {"type": "string", "pattern": r"^\d+(\.\d+)?:\d+$"},
    {"type": "string", "pattern": r"^[0-9]+(\.[0-9]+)?x[0-9]+$"},
    {"type": "string", "pattern": r"^\d+(\.\d{1,2})?$"},
    {"type": "string", "pattern": r"^[^:]+:[^:]+$"},
    {"type": "string", "pattern": r"^[A-Za-z0-9_-]{1,64}$"},
    {"type": "string", "pattern": r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"},
    {"type": "string", "pattern": r"^([A-Z]{3}) \d+$"},
    {"type": "string", "pattern": r"^SKU-\d{3,5}$", "minLength": 7},
    {"type": "array", "items": {"type": "string"}},
    {"type": "array", "items": LINE, "minItems": 1, "maxItems": 10000},
    {"type": "array", "items": {"type": "integer"}, "minItems": 3, "uniqueItems": True},
    {"type": "array", "maxItems": 0},
    {"type": "array", "minItems": 2},
    {"type": "array", "prefixItems": [{"type": "string"}, {"type": "integer"}], "items": False},
    {"$schema": DRAFT7, "type": "array", "items": [{"type": "string"}, {"type": "number"}], "minItems": 2},
    {
        "type": "object",
        "properties": {
            "lines": {"type": "array", "items": LINE},
            "giftCard": {"type": "number", "minimum": 0, "default": 0},
        },
        "required": ["lines"],
        "additionalProperties": False,
    },
    {
        "type": "object",
        "properties": {
            "sku": {"type": "string", "minLength": 1, "maxLength": 100, "pattern": r"^\S+$"},
            "price": {"description": "Decimal money amount, max 2 decimals", "type": ["string", "number"]},
            "qty": {"default": 1, "type": "integer", "minimum": 1, "maximum": 100000},
        },
        "required": ["sku", "price", "qty"],
        "additionalProperties": False,
    },
    {"type": "object", "properties": {}, "additionalProperties": False},
    {"type": "object", "properties": {"a": {"type": "string"}, "b": {"type": "integer"}}, "minProperties": 2},
    {"type": "object", "required": ["x"], "additionalProperties": {"type": "integer", "minimum": 4}},
    {
        "type": "object",
        "properties": {
            "steps": {
                "type": "array",
                "items": {"type": "object", "properties": {"op": {"enum": ["add", "show"]}}, "required": ["op"]},
            }
        },
        "required": ["steps"],
    },
    {
        "allOf": [
            {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]},
            {"required": ["b"], "properties": {"b": {"type": "integer"}}},
        ]
    },
    {"anyOf": [{"type": "null"}, {"type": "string", "minLength": 2}]},
    {"oneOf": [{"type": "string"}, {"type": "number", "minimum": 10}]},
    {"anyOf": [{"type": "string", "pattern": r"^\d+(\.\d{1,2})?$"}, {"type": "number", "minimum": 0}]},
    {
        "$defs": {"line": LINE},
        "type": "object",
        "properties": {"lines": {"type": "array", "items": {"$ref": "#/$defs/line"}, "minItems": 1}},
        "required": ["lines"],
    },
    {
        "$schema": DRAFT7,
        "definitions": {"node": {"type": "object", "properties": {"child": {"$ref": "#/definitions/node"}}}},
        "$ref": "#/definitions/node",
    },
    {},
    {"description": "anything"},
]


@pytest.mark.parametrize("schema", SCHEMAS, ids=[str(i) for i in range(len(SCHEMAS))])
def test_sample_validates(schema: dict[str, Any]) -> None:
    validator = validators.validator_for(schema)(schema, format_checker=FormatChecker())
    value = sample(schema)
    errors = [e.message for e in validator.iter_errors(value)]
    assert errors == [], f"{value!r}: {errors}"


def test_sample_prefers_numbers_for_mixed_types_and_unions() -> None:
    assert sample({"type": ["string", "number"]}) == 1
    assert sample({"anyOf": [{"type": "string"}, {"type": "integer", "minimum": 3}]}) == 3


def test_sample_uses_given_values_first() -> None:
    assert sample({"type": "integer", "default": 7}) == 7
    assert sample({"enum": ["a", "b"], "default": "b"}) == "b"
    assert sample({"const": None, "type": "string"}) is None


def test_sample_keeps_only_required_properties() -> None:
    schema = {"type": "object", "properties": {"a": {"type": "string"}, "b": {"type": "string"}}, "required": ["b"]}
    assert sample(schema) == {"b": "1"}


def test_sample_stops_at_recursive_refs() -> None:
    schema = {
        "$defs": {"n": {"type": "object", "properties": {"n": {"$ref": "#/$defs/n"}}, "required": ["n"]}},
        "$ref": "#/$defs/n",
    }
    value = sample(schema)
    depth = 0
    while isinstance(value, dict):
        value = value.get("n")
        depth += 1
    assert 3 < depth < 40


@pytest.mark.parametrize(
    "pattern",
    [
        r"^[a-z]{3}-\d{2}$",
        r"^(?:ab|cd)+$",
        r"^[^\s:]+$",
        r"^\w+@\w+\.com$",
        r"x{2,}y?z*",
        r"^[\d.]+$",
        r"^\(\d{3}\) \d{4}$",
        r"^(?<cur>[A-Z]{3}) \d+$",  # ECMA-262's named group, which Python spells (?P<
    ],
)
def test_regexgen_generates_a_match(pattern: str) -> None:
    value = regexgen.generate(pattern)
    assert value is not None
    assert regexgen.matches(pattern, value)


def test_regexgen_gives_up_cleanly() -> None:
    assert regexgen.generate(r"(?=.*\d)^[a-z]{3}$") is None  # a lookahead it can't satisfy
    assert regexgen.generate(r"[unclosed") is None
    assert not regexgen.matches(r"[unclosed", "x")
