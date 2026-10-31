import json
from pathlib import Path

import pytest

from analysis import longops, probes
from analysis.conftest import MakeFake
from analysis.result import Status
from analysis.tools import Call, MakeCall, pick_call, sampled

FAST = probes.Timing(reply=10, open=5, progress=5, start=2, stop=2, grace=0.5)
TOTAL = Call("cart_total", {"lines": [{"price": 12, "qty": 2}]})


def carts(folder: Path, count: int) -> Path:
    path = folder / f"carts-{count}.jsonl"
    path.write_text("".join(json.dumps({"id": f"c{i}", "lines": []}) + "\n" for i in range(count)))
    return path


def reprice(source: Path) -> MakeCall:
    return lambda tag: Call("reprice", {"carts": str(source), "output": str(source.with_name(f"{tag}.out"))})


def test_rpc_mode_passes_and_fails(fake: MakeFake) -> None:
    good = probes.rpc_mode(fake(), lambda _tag: TOTAL, FAST)
    assert good.status is Status.PASS
    assert good.detail == "malformed line → -32700; cart_total → result, with params._meta too"
    bad = probes.rpc_mode(fake(BAD="1"), lambda _tag: TOTAL, FAST)
    assert bad.status is Status.FAIL
    assert bad.detail.startswith("malformed line → no reply, not error -32700; process exited 1")


def test_rpc_mode_reports_a_failing_call_and_a_missing_one(fake: MakeFake) -> None:
    wrong = probes.rpc_mode(fake(), lambda _tag: Call("cart_total", {"bogus": 1}), FAST)
    assert wrong.status is Status.FAIL
    assert "error -32602" in wrong.detail
    assert "(data.code invalid_input)" in wrong.detail
    assert probes.rpc_mode(fake(), None, FAST).status is Status.UNMEASURED


@pytest.mark.parametrize(("mode", "style"), [("", "per-request _meta"), ("handshake", "initialize handshake")])
def test_mcp_mode_in_both_styles(fake: MakeFake, mode: str, style: str) -> None:
    result = probes.mcp_mode(fake(MCP=mode), pick_call, FAST)
    assert result.status is Status.PASS
    assert result.detail.startswith(f"{style}, 4 tools; cart_total → result: ")


def test_mcp_mode_fails(fake: MakeFake) -> None:
    missing = probes.mcp_mode(fake(BAD="1"), pick_call, FAST)
    assert missing.status is Status.FAIL
    assert "process exited 2, stderr: unknown command: mcp" in missing.detail
    erring = probes.mcp_mode(fake(), lambda tools: sampled(next(t for t in tools if t.name == "reprice")), FAST)
    assert erring.status is Status.FAIL
    assert "isError" in erring.detail
    unpicked = probes.mcp_mode(fake(), lambda _tools: "no re-pricing tool", FAST)
    assert unpicked.status is Status.UNMEASURED


def test_finishes(fake: MakeFake, tmp_path: Path) -> None:
    done = probes.finishes(fake(), reprice(carts(tmp_path, 10)), 10)
    assert done.status is Status.PASS
    assert done.detail.endswith('result {"carts": 10}')
    slow = probes.finishes(fake(DELAY="1"), reprice(carts(tmp_path, 10)), 1)
    assert slow.status is Status.FAIL
    assert slow.detail.startswith("no result in 1 s")
    missing = probes.finishes(fake(), reprice(tmp_path / "missing.jsonl"), 10)
    assert missing.status is Status.FAIL
    assert "error -32602" in missing.detail


def test_progress_rpc(fake: MakeFake, tmp_path: Path) -> None:
    source = carts(tmp_path, 40)
    sent = longops.progress_rpc(fake(DELAY="0.05"), reprice(source), FAST)
    assert sent.status is Status.PASS
    assert '"progressToken": "bench-progress"' in sent.detail
    silent = longops.progress_rpc(fake(BAD="1", DELAY="0.01"), reprice(source), FAST)
    assert silent.status is Status.FAIL
    assert silent.detail.startswith("reply after")
    assert "no notifications" in silent.detail


def test_progress_mcp(fake: MakeFake, tmp_path: Path) -> None:
    source = carts(tmp_path, 40)
    assert longops.progress_mcp(fake(DELAY="0.05", MCP="handshake"), reprice(source), FAST).status is Status.PASS
    assert longops.progress_mcp(fake(BAD="1"), reprice(source), FAST).status is Status.UNMEASURED


def test_cancel_rpc(fake: MakeFake, tmp_path: Path) -> None:
    source = carts(tmp_path, 400)
    later = Call("reprice", {"carts": str(tmp_path / "missing.jsonl"), "output": str(tmp_path / "later.out")})
    stopped = longops.cancel_rpc(fake(DELAY="0.05"), reprice(source), later, FAST)
    assert stopped.status is Status.PASS
    assert stopped.detail.startswith("error -32800 cancelled")
    assert "a later call got error -32602" in stopped.detail
    going = longops.cancel_rpc(fake(DELAY="0.05", CANCEL="ignore"), reprice(source), later, FAST)
    assert going.status is Status.FAIL
    assert "notifications/progress more than" in going.detail
    quick = longops.cancel_rpc(fake(), reprice(carts(tmp_path, 2)), later, FAST)
    assert quick.status is Status.UNMEASURED
    assert "before it could be cancelled" in quick.detail


def test_cancel_mcp(fake: MakeFake, tmp_path: Path) -> None:
    source = carts(tmp_path, 400)
    stopped = longops.cancel_mcp(fake(DELAY="0.05"), reprice(source), FAST)
    assert stopped.status is Status.PASS
    assert stopped.detail.endswith("tools/list answered")
    replied = longops.cancel_mcp(fake(DELAY="0.05", CANCEL="reply"), reprice(source), FAST)
    assert replied.status is Status.FAIL
    assert replied.detail.startswith("replied to the cancelled call")
    going = longops.cancel_mcp(fake(DELAY="0.05", CANCEL="ignore"), reprice(source), FAST)
    assert going.status is Status.FAIL
    assert "notifications/progress more than" in going.detail
