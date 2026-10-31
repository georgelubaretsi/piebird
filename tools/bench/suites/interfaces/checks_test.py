import json
from pathlib import Path
from typing import Any

import analysis
import pytest
from analysis.main import main
from analysis.tools import Tool
from suites.interfaces import checks

FAKE = Path(analysis.__file__).parent / "testdata" / "fake_program.py"
PATH = {"type": "string", "minLength": 1}


def tool(name: str, props: dict[str, Any], required: list[str] | None = None) -> Tool:
    schema = {"type": "object", "properties": props, "required": required if required is not None else list(props)}
    return Tool(name, schema)


# Re-pricing schemas of past runs, and what the probe should take from them.
@pytest.mark.parametrize(
    ("tools", "found"),
    [
        ([tool("reprice", {"export": PATH, "output": PATH})], ("reprice", "export", "output")),
        ([tool("reprice", {"carts": PATH, "output": PATH})], ("reprice", "carts", "output")),
        (
            [tool("reprice", {"carts": PATH, "output": PATH, "overwrite": {"type": "boolean"}}, ["carts", "output"])],
            ("reprice", "carts", "output"),
        ),
        (
            [
                tool(
                    "reprice", {"source": PATH, "output": PATH, "onError": {"type": "string", "enum": ["fail", "skip"]}}
                )
            ],
            ("reprice", "source", "output"),
        ),
        ([tool("repriceCarts", {"inputPath": PATH, "outputPath": PATH})], ("repriceCarts", "inputPath", "outputPath")),
        ([tool("run_job", {"in": PATH, "out": PATH})], ("run_job", "in", "out")),
        (
            [
                tool("export_report", {"source": PATH, "destination": PATH}),
                tool("price_export", {"file": PATH, "to": PATH}),
            ],
            ("price_export", "file", "to"),
        ),
    ],
)
def test_find_reprice(tools: list[Tool], found: tuple[str, str, str]) -> None:
    reprice = checks.find_reprice(tools)
    assert isinstance(reprice, checks.Reprice)
    assert (reprice.tool.name, reprice.source, reprice.output) == found


def test_find_reprice_says_what_it_saw() -> None:
    tools = [tool("add_line", {"sku": PATH, "price": {"type": "number"}}), tool("reprice", {"carts": PATH})]
    assert (
        checks.find_reprice(tools)
        == "no tool takes a source file and an output file: add_line(sku, price); reprice(carts)"
    )


def test_reprice_calls_keep_other_required_arguments(tmp_path: Path) -> None:
    reprice = checks.find_reprice(
        [tool("reprice", {"source": PATH, "output": PATH, "onError": {"enum": ["fail", "skip"]}})]
    )
    assert isinstance(reprice, checks.Reprice)
    call = reprice.maker(tmp_path / "in.jsonl", tmp_path)("first")
    assert call.args == {
        "source": str(tmp_path / "in.jsonl"),
        "output": str(tmp_path / "first.jsonl"),
        "onError": "fail",
    }


@pytest.mark.parametrize(
    ("props", "key"),
    [
        ({"price": {"type": "number"}, "qty": {"type": "integer"}, "name": {"type": "string"}}, "name"),
        (
            {
                "sku": {"type": "string", "pattern": r"^\S+$"},
                "price": {"type": ["string", "number"]},
                "qty": {"type": "integer"},
            },
            "sku",
        ),
        ({"cartId": {"type": "string"}, "title": {"type": "string"}, "price": {"type": "number"}}, "title"),
        ({"session": {"type": "string"}, "note": {"type": "string"}}, "note"),
        ({"price": {"type": "string"}, "qty": {"type": "integer"}}, None),
    ],
)
def test_item_key(props: dict[str, Any], key: str | None) -> None:
    assert checks.item_key(tool("add", props)) == key


@pytest.mark.parametrize(
    ("names", "show"),
    [
        (["add_line", "remove_line", "apply_coupon", "show"], "show"),
        (["add-line", "remove-line", "apply-gift-card", "set-shipping", "get-total"], "get-total"),
        (["cart_add", "cart_remove", "cart_show", "cart_reset"], "cart_show"),
        (["add", "remove"], None),
    ],
)
def test_show_tool(names: list[str], show: str | None) -> None:
    tools = [tool(n, {}) for n in names]
    found = checks.show_tool(tools, tools[0])
    assert (found.name if found else None) == show


@pytest.mark.parametrize(
    ("result", "found"),
    [
        ({"cartId": "c1", "total": 3}, "c1"),
        ({"session_id": 4}, 4),
        ({"cart": {"id": 7, "lines": []}}, 7),
        ({"lines": [{"id": 1}]}, None),
        ({"id": True}, None),
        ("text", None),
    ],
)
def test_cart_id(result: object, found: object) -> None:
    assert checks.cart_id(result) == found


def test_every_suite_check_has_an_implementation() -> None:
    suite = json.loads((Path(checks.__file__).parent / "suite.json").read_text())
    named = {c for task in suite["tasks"].values() for c in task["checks"]}
    assert named <= set(checks.CHECKS)


def scored_fake(tmp_path: Path) -> dict[str, dict[str, str]]:
    """Scores one run whose program is the fake, with the suite's real checks."""
    out = tmp_path / "out"
    run = out / "runs" / "v.t.1"
    project = run / "project"
    project.mkdir(parents=True)
    (project / "package.json").write_text(json.dumps({"name": "shop", "bin": {"fake": "fake.py"}}))
    (project / "fake.py").write_text("#!/usr/bin/env python3\n" + FAKE.read_text())
    (project / "fake.py").chmod(0o755)
    meta = {"id": "v.t.1", "variant": "v", "task": "t", "repeat": 1, "exitCode": 0, "timedOut": False, "seconds": 1}
    (run / "meta.json").write_text(json.dumps(meta))
    names = ["named", "help", "version", "help-json", "bad-flag", "cli-input", "rpc", "mcp", "session"]
    suite = {
        "name": "interfaces",
        "root": str(Path(checks.__file__).parent),
        "guide": "rules/interfaces.md",
        "tasks": {"t": {"checks": names}},
    }
    (out / "suite.json").write_text(json.dumps(suite))
    assert main(["--", str(out)]) == 0
    return json.loads((out / "results.json").read_text())["runs"][0]["checks"]  # type: ignore[no-any-return]  # JSON


def test_checks_pass_a_program_keeping_the_contract(tmp_path: Path) -> None:
    got = scored_fake(tmp_path)
    assert {name: c["status"] for name, c in got.items() if c["status"] != "pass"} == {}
    assert got["rpc"]["detail"] == "malformed line → -32700; reprice → result, with params._meta too"
    assert got["session"]["detail"] == "add_line tee, mug; show lists both"


def test_checks_fail_a_program_breaking_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_BAD", "1")
    got = scored_fake(tmp_path)
    assert {name: c["status"] for name, c in got.items()} == {
        "named": "pass",
        "help": "fail",
        "version": "fail",
        "help-json": "fail",
        "bad-flag": "fail",
        "cli-input": "unmeasured",
        "rpc": "fail",
        "mcp": "fail",
        "session": "unmeasured",
    }


def test_session_fails_when_the_cart_forgets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_FORGET", "1")
    session = scored_fake(tmp_path)["session"]
    assert session["status"] == "fail"
    assert session["detail"] == 'show after adding tee and mug → result {"lines": []}: no tee, mug'


def test_session_passes_the_cart_id_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_CARTS", "1")
    session = scored_fake(tmp_path)["session"]
    assert session == {"status": "pass", "detail": "add_line tee, mug (cart c1); show lists both"}


def test_show_tool_prefers_show_words_over_a_stateless_total() -> None:
    tools = [
        tool("add_line", {"sku": PATH}),
        tool("cart_total", {"lines": {"type": "array"}}),
        tool("show", {"cartId": PATH}),
    ]
    found = checks.show_tool(tools, tools[0])
    assert found is not None
    assert found.name == "show"
