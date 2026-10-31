import json
from pathlib import Path

import pytest

from analysis import clicheck
from analysis.conftest import MakeFake
from analysis.result import Status
from analysis.tools import Tool


def test_good_program_passes_every_cli_check(fake: MakeFake, tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(json.dumps({"name": "shop", "bin": {"fake": "fake.py"}}))
    program = fake()
    assert clicheck.named(program).detail == "fake (package.json bin)"
    assert clicheck.help_text(program).status is Status.PASS
    assert clicheck.version(program).detail == "'fake 1.0.0'"
    tools = clicheck.tool_definitions(program)
    assert clicheck.help_json(tools).detail == "4 tools: cart_total, add_line, show, reprice"
    assert clicheck.bad_flag(program).status is Status.PASS
    cli = clicheck.cli_input(program, tools)
    assert cli.status is Status.PASS
    assert cli.detail == "cart_total via `total`, show via `show`; not mapped: add_line, reprice"


def test_broken_program_fails_every_cli_check(fake: MakeFake) -> None:
    program = fake(BAD="1")
    help_result = clicheck.help_text(program)
    assert help_result.status is Status.FAIL
    assert "no example" in help_result.detail
    assert "--version exit 1" in clicheck.version(program).detail
    tools = clicheck.tool_definitions(program)
    assert isinstance(tools, str)
    assert "stdout isn't JSON" in tools
    assert clicheck.help_json(tools).status is Status.FAIL
    bad = clicheck.bad_flag(program)
    assert bad.status is Status.FAIL
    assert "exit 0" in bad.detail
    assert clicheck.cli_input(program, tools).status is Status.UNMEASURED


def test_cli_input_fails_on_a_wrong_invalid_input_reply(fake: MakeFake) -> None:
    good_tools = clicheck.tool_definitions(fake())
    assert not isinstance(good_tools, str)
    result = clicheck.cli_input(fake(BAD="1"), good_tools)
    assert result.status is Status.FAIL
    assert result.detail.startswith('cart_total via `total`: {"bogus": 1} → exit 1')
    assert "stderr has no {error: {code, message}}" in result.detail


def test_cli_input_fails_when_a_command_named_in_help_rejects_valid_input(fake: MakeFake) -> None:
    keyed_by_flags = Tool("total", {"type": "object", "properties": {"line": {"type": "array"}}, "required": ["line"]})
    result = clicheck.cli_input(fake(), [keyed_by_flags])
    assert result.status is Status.FAIL
    assert result.detail.startswith("total via `total`: valid input '{\"line\": []}' → exit 2")


def test_cli_input_is_unmeasured_when_no_tool_maps(fake: MakeFake) -> None:
    tools = [Tool("frobnicate_widgets", {"type": "object"}), Tool("polish", {"type": "object"})]
    result = clicheck.cli_input(fake(), tools)
    assert result.status is Status.UNMEASURED
    assert "frobnicate_widgets: frobnicate_widgets | frobnicate widgets" in result.detail


def test_cli_input_maps_a_lone_tool_to_the_bare_program(fake: MakeFake) -> None:
    result = clicheck.cli_input(fake(), [Tool("quote", {"type": "object"})])
    assert result.status is Status.FAIL
    assert result.detail.startswith("quote via `(no command words)`: valid input '{}' → exit 2")


def test_named_without_package_uses_the_usage_line(fake: MakeFake) -> None:
    assert clicheck.named(fake()).detail == "fake (usage line of --help; no package.json bin)"


def test_named_ignores_generic_scripts(fake: MakeFake, tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"test": "bun test", "build": "x"}}))
    assert clicheck.named(fake(BAD="1")).status is Status.FAIL


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("total", [["total"], []]),
        ("cart_total", [["cart_total"], ["cart", "total"], ["total"], ["cart-total"], []]),
        ("apply-gift-card", [["apply-gift-card"], ["apply", "gift", "card"], []]),
        ("applyCoupon", [["applyCoupon"], ["apply-coupon"], ["apply", "coupon"], []]),
    ],
)
def test_word_candidates(name: str, expected: list[list[str]]) -> None:
    assert clicheck.word_candidates(name) == expected


def test_tool_definitions_need_exit_0(fake: MakeFake) -> None:
    tools = clicheck.tool_definitions(fake(HELP_JSON_EXIT="1"))
    assert isinstance(tools, str)
    assert tools.startswith('--help --json exit 1, stdout \'{"tools": [')
    assert clicheck.help_json(tools).status is Status.FAIL
    assert clicheck.cli_input(fake(), tools).status is Status.UNMEASURED
