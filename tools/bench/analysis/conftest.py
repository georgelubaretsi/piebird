import os
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from analysis.program import Program

FAKE = Path(__file__).parent / "testdata" / "fake_program.py"

type MakeFake = Callable[..., Program]


@pytest.fixture
def fake(tmp_path: Path) -> MakeFake:
    """The fake program (testdata/fake_program.py) with FAKE_* settings, e.g. `fake(BAD="1")`."""

    def make(**settings: str) -> Program:
        env = dict(os.environ, **{f"FAKE_{k}": v for k, v in settings.items()})
        return Program(tmp_path, (sys.executable, str(FAKE)), FAKE.name, "test", env)

    return make
