---
description: You MUST read this before building or changing any CLI, UI or API; it defines the required contract (JSON in and out, exit codes, errors, MCP tool list)
---
# Interfaces

Every program you build, for yourself or others; not one-off scripts. Agents and scripts are
among its users even when the request mentions only people. Existing conventions win.

- One declaration per operation: JSON Schema in and out, checked on every call, plus read-only,
  destructive, idempotent, open-world. Pure core; every operation, settings included, is
  reachable headless; UI, CLI, RPC and MCP are thin adapters.
- CLI, per clig.dev. Even if nobody uses the CLI yet, assume someone will, and design it that way:
  a real name, help with an example, `-h`, `--version`. `--json` (one value on stdout, later
  versions only add); `--input <file|->` (the input as JSON, keyed as in its schema; flags are
  those names in kebab-case); `--help --json` prints the MCP tool definitions; exit 0 success, 2
  invalid input, 1 otherwise; `--json` errors on stderr as `{"error": {"code": …, "message": …}}`;
  when input is needed without a TTY or with `--no-input`, fail saying what to run; lists page;
  large results go to a file. Secrets: stdin, then the system credential store (CI, containers:
  the platform's secret mount); never flags, environment variables, files or output.

## Sessions

A program with live state between calls, or an operation that can take more than a few seconds,
must also run as one long-lived process in two modes, from the same declarations, through existing
libraries; adding them is part of the task, not a follow-up:

- `<program> rpc`: JSON-RPC 2.0, one message per line. Method = operation name, params = input
  (`params._meta` is protocol metadata, removed before validation), result = output. Errors carry
  our code in `data.code`; a malformed line gets -32700 and the loop goes on.
- `<program> mcp`: the official MCP SDK over stdio.

Live state stays in that process; data that should outlive it gets an id one-shot commands accept.
Long operations send `notifications/progress` when `_meta.progressToken` is set and stop on
`notifications/cancelled` (`requestId`), with those exact names, in both modes. A decision needed
mid-way: MCP's `input_required` in `mcp`, otherwise an argument or a clear failure.
