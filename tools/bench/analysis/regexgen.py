"""A short string a JSON Schema `pattern` accepts, for the patterns tool schemas use (pure).

Best effort: literals, `.`, classes (`[a-z0-9_-]`, `[^:]`), the escapes `\\d \\w \\s` and their
negations, groups with alternation (the first branch), and the quantifiers `? * + {n} {n,} {n,m}`,
each taken at its minimum. Lookarounds and backreferences generate nothing; the caller checks the
result against the pattern and falls back when it doesn't match.
"""

import re

PREFERRED = "1ax-_A0 :."
ESCAPES = {"d": "1", "w": "a", "s": " ", "D": "a", "W": "-", "S": "a", "b": "", "B": ""}
LITERAL_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "f": "\f", "v": "\v", "0": "\0"}
MAX_REPEAT = 64


class _Parser:
    def __init__(self, pattern: str) -> None:
        self.text = pattern
        self.at = 0

    def peek(self) -> str:
        return self.text[self.at] if self.at < len(self.text) else ""

    def take(self) -> str:
        char = self.peek()
        self.at += 1
        return char

    def alternation(self) -> str:
        first = self.sequence()
        while self.peek() == "|":
            self.take()
            self.sequence()  # parsed for position only: the first branch is used
        return first

    def sequence(self) -> str:
        out: list[str] = []
        while self.peek() not in ("", "|", ")"):
            atom = self.atom()
            out.append(atom * self.repeat())
        return "".join(out)

    def atom(self) -> str:
        char = self.take()
        if char == "(":
            return self.group()
        if char == "[":
            return self.char_class()
        if char == "\\":
            return self.escape()
        if char in "^$":
            return ""
        return "a" if char == "." else char

    def group(self) -> str:
        lookaround = False
        if self.peek() == "?":
            self.take()
            kind = self.take()
            if kind == "<" and self.peek() not in "=!":
                while self.take() not in ("", ">"):
                    pass  # a named group: skip its name
            elif kind in "=!<":
                lookaround = True
                if kind == "<":
                    self.take()
            elif kind == "P" and self.peek() == "<":
                while self.take() not in ("", ">"):
                    pass
        inner = self.alternation()
        self.take()  # ")"
        return "" if lookaround else inner

    def escape(self) -> str:
        char = self.take()
        if char in ESCAPES:
            return ESCAPES[char]
        if char.isdigit() and char != "0":
            return ""  # a backreference
        return LITERAL_ESCAPES.get(char, char)

    def char_class(self) -> str:
        negated = self.peek() == "^"
        if negated:
            self.take()
        members: set[str] = set()
        first = True
        while self.peek() and (self.peek() != "]" or first):
            first = False
            low = self.class_char(members)
            if self.peek() == "-" and self.text[self.at + 1 : self.at + 2] not in ("]", ""):
                self.take()
                high = self.class_char(members)
                members.update(chr(c) for c in range(ord(low or " "), ord(high or " ") + 1))
            elif low:
                members.add(low)
        self.take()  # "]"
        return _choose(members, negated)

    def class_char(self, members: set[str]) -> str:
        """One member; an escape like `\\d` adds its own members and returns ""."""
        char = self.take()
        if char != "\\":
            return char
        code = self.take()
        sets = {"d": "0123456789", "w": "abcxyzABC0123456789_", "s": " \t"}
        if code in sets:
            members.update(sets[code])
            return ""
        if code in ("D", "W", "S"):
            members.update("a-" if code != "S" else "a1")
            return ""
        return LITERAL_ESCAPES.get(code, code)

    def repeat(self) -> int:
        char = self.peek()
        count = 1
        if char in "*?":
            self.take()
            count = 0
        elif char == "+":
            self.take()
        elif char == "{":
            match = re.match(r"\{(\d+)(,\d*)?\}", self.text[self.at :])
            if not match:
                return 1  # a literal brace
            self.at += match.end()
            count = int(match.group(1))
        if self.peek() in ("?", "+"):
            self.take()  # lazy or possessive
        return min(count, MAX_REPEAT)


def _choose(members: set[str], negated: bool) -> str:
    if not negated:
        preferred = next((c for c in PREFERRED if c in members), None)
        return preferred or (min(members) if members else "")
    return next((c for c in PREFERRED + "bcdefg" if c not in members), "")


def generate(pattern: str) -> str | None:
    """A string matching `pattern`, or None when the pattern is outside the supported subset."""
    try:
        compiled = re.compile(python_pattern(pattern))
        value = _Parser(pattern).alternation()
    except re.error, IndexError, ValueError:
        return None
    return value if compiled.search(value) else None


def python_pattern(pattern: str) -> str:
    """ECMA-262 named groups `(?<name>` in Python's spelling; the rest is shared syntax."""
    return re.sub(r"\(\?<([A-Za-z_])", r"(?P<\1", pattern)


def matches(pattern: str, value: str) -> bool:
    """JSON Schema semantics: unanchored search. A pattern Python can't compile matches nothing."""
    try:
        return re.search(python_pattern(pattern), value) is not None
    except re.error:
        return False
