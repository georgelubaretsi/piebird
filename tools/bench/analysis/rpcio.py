"""A JSON-RPC 2.0 client over a subprocess's stdin and stdout, one message per line.

A reader thread parses stdout into messages as they come, so waits never block on a pipe; a
second thread drains stderr (a full pipe would stall the program) and keeps its tail.
Notifications and requests from the program are kept with their arrival time. Closing kills the
program's whole process group.
"""

import contextlib
import json
import os
import subprocess
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import IO, Self

from analysis.program import Command, kill_group

type Message = dict[str, object]
type RequestId = int | str | None
STDERR_TAIL = 4000


@dataclass(frozen=True, slots=True)
class Received:
    at: float  # time.monotonic() on arrival
    message: Message


class LineRpc:
    def __init__(self, command: Command) -> None:
        self._proc = subprocess.Popen(
            command.argv,
            cwd=command.cwd,
            env=dict(command.env),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        self._lock = threading.Condition()
        self._messages: list[Received] = []  # every JSON object on stdout, in arrival order
        self._taken: set[int] = set()  # replies wait() has returned
        self.junk: list[str] = []  # stdout lines that aren't JSON objects
        self._stderr: deque[str] = deque(maxlen=STDERR_TAIL)
        self._eof = False
        self._next_id = 0
        self._threads = [
            threading.Thread(target=self._read_stdout, daemon=True),
            threading.Thread(target=self._read_stderr, daemon=True),
        ]
        for thread in self._threads:
            thread.start()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def send_raw(self, line: str) -> bool:
        """Writes one line; False when the program no longer reads its stdin."""
        stdin = self._proc.stdin
        if stdin is None:
            return False
        try:
            stdin.write((line + "\n").encode())
            stdin.flush()
        except BrokenPipeError, ValueError, OSError:
            return False
        return True

    def send(self, method: str, params: object, request_id: RequestId = None) -> RequestId:
        if request_id is None:
            self._next_id += 1
            request_id = self._next_id
        self.send_raw(json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}))
        return request_id

    def notify(self, method: str, params: object) -> None:
        self.send_raw(json.dumps({"jsonrpc": "2.0", "method": method, "params": params}))

    def call(self, method: str, params: object, timeout: float = 30.0) -> Message | None:
        return self.wait(self.send(method, params), timeout)

    def wait(self, request_id: RequestId, timeout: float) -> Message | None:
        """The reply to `request_id` (None: a reply with a null id), each returned once;
        None on timeout, or once the program has closed its stdout."""
        found = self.wait_for(lambda r: is_reply(r.message, request_id), timeout, take=True)
        return found.message if found else None

    def wait_for(self, matches: Callable[[Received], bool], timeout: float, *, take: bool = False) -> Received | None:
        """The first message that `matches` (with `take`, one not taken before, then taken)."""
        end = time.monotonic() + timeout
        with self._lock:
            while (found := self._find(matches, take=take)) is None:
                left = end - time.monotonic()
                if left <= 0 or self._eof:
                    return None
                self._lock.wait(left)
            return found

    def _find(self, matches: Callable[[Received], bool], *, take: bool) -> Received | None:
        for i, received in enumerate(self._messages):
            if i not in self._taken and matches(received):
                if take:
                    self._taken.add(i)
                return received
        return None

    @property
    def notes(self) -> list[Received]:
        """Messages with a method: the program's notifications and requests."""
        with self._lock:
            return [r for r in self._messages if "method" in r.message]

    def alive(self) -> bool:
        return self._proc.poll() is None

    @property
    def exit_code(self) -> int | None:
        return self._proc.poll()

    def stderr_tail(self) -> str:
        with self._lock:
            return "".join(self._stderr)

    def state(self) -> str:
        """Whether the program still runs, for details."""
        code = self.exit_code
        if code is None:
            return "process still running"
        return f"process exited {code}, stderr: {_tail(self.stderr_tail())}"

    def close(self) -> None:
        if self._proc.stdin is not None:
            with contextlib.suppress(OSError):  # the program already closed it
                self._proc.stdin.close()
        kill_group(self._proc)
        with contextlib.suppress(subprocess.TimeoutExpired):  # unkillable for now; the threads are daemons
            self._proc.wait(timeout=5)
        for thread in self._threads:
            thread.join(timeout=2)

    def _read_stdout(self) -> None:
        stream: IO[bytes] | None = self._proc.stdout
        for raw in stream or []:
            line = raw.decode(errors="replace").strip()
            if not line:
                continue
            message = _parse(line)
            with self._lock:
                if message is None:
                    self.junk.append(line)
                else:
                    self._messages.append(Received(time.monotonic(), message))
                self._lock.notify_all()
        with self._lock:
            self._eof = True
            self._lock.notify_all()

    def _read_stderr(self) -> None:
        stream: IO[bytes] | None = self._proc.stderr
        if stream is None:
            return
        while chunk := _read_chunk(stream):
            with self._lock:
                self._stderr.extend(chunk.decode(errors="replace"))


def _read_chunk(stream: IO[bytes]) -> bytes:
    try:
        return os.read(stream.fileno(), 4096)
    except OSError, ValueError:
        return b""


def error_of(message: Message | None) -> dict[str, object] | None:
    error = message.get("error") if message else None
    return error if isinstance(error, dict) else None


def describe(message: Message | None) -> str:
    """A reply for a detail: `result {...}` or `error -32602 message`."""
    if message is None:
        return "no reply"
    error = error_of(message)
    if error is not None:
        data = error.get("data")
        ours = f" (data.code {data['code']})" if isinstance(data, dict) and "code" in data else ""
        return f"error {error.get('code')} {_tail(str(error.get('message', '')))}{ours}"
    return f"result {_tail(json.dumps(message.get('result')))}"


def is_reply(message: Message, request_id: RequestId) -> bool:
    return message.get("id") == request_id and ("result" in message or "error" in message)


def has_result(message: Message | None) -> bool:
    return message is not None and "result" in message and "error" not in message


def _parse(line: str) -> Message | None:
    try:
        value: object = json.loads(line)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def _tail(text: str, limit: int = 160) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"
