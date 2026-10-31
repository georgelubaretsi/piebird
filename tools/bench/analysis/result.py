"""A check's outcome: pass, fail or unmeasured, with one line saying what was seen."""

import enum
import re
from dataclasses import dataclass

DETAIL_LIMIT = 400


class Status(enum.StrEnum):
    PASS = "pass"
    FAIL = "fail"
    UNMEASURED = "unmeasured"


@dataclass(frozen=True, slots=True)
class Result:
    """`detail` is one line; it is required for `fail` and `unmeasured`."""

    status: Status
    detail: str = ""

    def __post_init__(self) -> None:
        line = one_line(self.detail)
        if self.status is not Status.PASS and not line:
            raise ValueError(f"a {self.status} result needs a detail")
        object.__setattr__(self, "detail", line)


def passed(detail: str = "") -> Result:
    return Result(Status.PASS, detail)


def failed(detail: str) -> Result:
    return Result(Status.FAIL, detail)


def unmeasured(detail: str) -> Result:
    return Result(Status.UNMEASURED, detail)


def one_line(text: str, limit: int = DETAIL_LIMIT) -> str:
    """Whitespace runs collapsed to one space, cut at `limit` characters."""
    line = re.sub(r"\s+", " ", text).strip()
    return line if len(line) <= limit else line[: limit - 1] + "…"


def excerpt(text: str, limit: int = 160) -> str:
    """A program's output for a detail: lines joined with ` | `, quoted, cut at `limit`."""
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    if not lines:
        return "(empty)"
    joined = " | ".join(lines)
    cut = joined if len(joined) <= limit else joined[: limit - 1] + "…"
    return f"'{cut}'"
