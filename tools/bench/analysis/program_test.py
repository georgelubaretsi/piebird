import json
import os
import sys
import time
from pathlib import Path

from analysis.program import Command, Finder, Program, changed_files, execute

DIFF = """diff --git a/src/cli.ts b/src/cli.ts
new file mode 100644
--- /dev/null
+++ b/src/cli.ts
@@ -0,0 +1 @@
+if (import.meta.main) main();
diff --git a/node_modules/x/index.js b/node_modules/x/index.js
+++ b/node_modules/x/index.js
diff --git a/src/cart.ts b/src/cart.ts
--- a/src/cart.ts
+++ b/src/cart.ts
"""


def write(folder: Path, files: dict[str, str]) -> None:
    for name, text in files.items():
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text(text)


def finder(project: Path) -> Finder:
    return Finder(project, dict(os.environ), "/bin/bun-for-test")


def test_changed_files_skips_node_modules() -> None:
    assert changed_files(DIFF) == ["src/cli.ts", "src/cart.ts"]


def test_find_prefers_package_bin(tmp_path: Path) -> None:
    write(
        tmp_path,
        {
            "package.json": json.dumps({"bin": {"cart": "./src/main.ts"}}),
            "src/main.ts": "",
            "src/cli.ts": "process.argv",
        },
    )
    found = finder(tmp_path).find(["src/cli.ts"])
    assert isinstance(found, Program)
    assert (found.entry, found.how, found.argv) == (
        "src/main.ts",
        "package.json bin cart",
        ("/bin/bun-for-test", "src/main.ts"),
    )


def test_find_falls_back_to_a_changed_file_reading_argv(tmp_path: Path) -> None:
    files = {
        "package.json": json.dumps({"bin": "gone.ts"}),
        "src/cart.ts": "export const x = 1;",
        "src/run-cart.ts": "Bun.argv",
        "src/cli.ts": "if (import.meta.main) {}",
        "src/cli.test.ts": "process.argv",
    }
    write(tmp_path, files)
    found = finder(tmp_path).find(["src/cart.ts", "src/run-cart.ts", "src/cli.test.ts", "src/cli.ts"])
    assert isinstance(found, Program)
    assert (found.entry, found.how) == ("src/cli.ts", "changed file reading argv")


def test_find_runs_other_entries_directly(tmp_path: Path) -> None:
    write(tmp_path, {"package.json": json.dumps({"name": "cart", "bin": "bin/cart"}), "bin/cart": "#!/bin/sh\n"})
    found = finder(tmp_path).find([])
    assert isinstance(found, Program)
    assert found.argv == (str(tmp_path / "bin" / "cart"),)


def test_find_says_what_it_looked_at(tmp_path: Path) -> None:
    write(tmp_path, {"package.json": json.dumps({"bin": {"cart": "src/gone.ts"}}), "src/cart.ts": "export {}"})
    found = Finder(tmp_path, dict(os.environ), sys.executable).find(["src/cart.ts", "src/missing.ts"])
    assert (
        found
        == "no program: package.json bin src/gone.ts missing; 1 changed source files, none reads argv or prints tools"
    )


def test_find_without_bun(tmp_path: Path) -> None:
    write(tmp_path, {"package.json": json.dumps({"bin": {"cart": "cli.ts"}}), "cli.ts": ""})
    assert Finder(tmp_path, {}, None).find([]) == "cli.ts needs bun, which isn't on PATH"


def test_execute_passes_stdin_and_reports_exit(tmp_path: Path) -> None:
    command = Command(
        (sys.executable, "-c", "import sys; print(sys.stdin.read().upper()); sys.exit(3)"), tmp_path, dict(os.environ)
    )
    done = execute(command, stdin="abc")
    assert (done.exit_code, done.stdout.strip(), done.exit_text) == (3, "ABC", "exit 3")


def test_execute_kills_the_whole_group_at_the_timeout(tmp_path: Path) -> None:
    marker = tmp_path / "survived"
    script = f"sleep 3 && touch {marker} & echo started; sleep 30"
    start = time.monotonic()
    done = execute(Command(("/bin/sh", "-c", script), tmp_path, dict(os.environ)), timeout=0.5)
    assert done.exit_code is None
    assert done.exit_text == "timed out"
    assert done.stdout.strip() == "started"
    assert time.monotonic() - start < 10
    time.sleep(3.5)
    assert not marker.exists(), "a child outlived the timeout"
