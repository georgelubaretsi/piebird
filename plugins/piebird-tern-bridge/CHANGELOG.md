# Changelog

All notable changes to this plugin are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/2.0.0/),
and this plugin adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- In Tern only, a part of every agent's system prompt (`in-tern` in `core/model.ftl`): read the
  `tern` skill before working with panes, tabs, sessions or Tern agents, and keep omp subagents
  (`task`) apart from Tern agents in panes.
- Tool `tern_lua`: run Lua in the Tern window that holds omp's pane, with Tern's window API
  (`cx`): Tern agents in other panes, sessions and layout, block reads, git, SQLite, notebooks,
  boards, browser, settings and toasts. Returns the first value as JSON, waits on a returned
  Awaitable (`timeout_s`, default 130 s, max 600 s), keeps a `state` table between calls and
  returns `print` output.
- Offered only inside Tern (`TERM_PROGRAM=tern`) on macOS and Linux, and not in a remote host's
  panes.
- Tern plugin `piebird-tern-bridge` (folder `so.stencil.tern/`), the Tern half of the tool. omp
  installs it: when omp starts as the main agent in a local Tern pane, it installs the Tern
  half if Tern lacks it, replaces a copy of another version (after a plugin upgrade), and says
  so in the chat. A linked Tern half and one turned off in Tern's settings are left alone. The
  tool says how to install it by hand when it's missing.
- Safe failure handling: a call that overruns Tern's 50 ms plugin budget is reported as
  "outcome unknown", never retried, and Tern's plugins are reloaded so the next call can run.
- macOS App Nap check: when a background Tern stalls the bridge, the tool tells you to run
  `defaults write so.stencil.tern NSAppSleepDisabled -bool YES` and restart Tern.
- Skill `tern`: how to work with Tern agents (separate from omp subagents), panes, blocks,
  layout and settings through the `tern` CLI and `tern_lua`, with common calls and rules.
- Every word the model reads from `tern_lua` (its description, its answers, errors and hints) is
  in `core/model.ftl`; [what the model sees](../../docs/model/piebird-tern-bridge.md) shows each,
  with that part and the skill. omp approves the tool as code execution.
- Supported hosts: omp, and Tern through omp.
- README, with a demo video: omp opens a file beside itself, then starts a Tern agent and reads
  its answer.

### Changed

- The Tern part of the system prompt (was the rule `tern-agents`) reaches agents only inside
  Tern, from the plugin's omp extension along with `tern_lua`; outside Tern, omp gets none of it.
- `tern_lua` failing in the plugin's own code tells the model so in the plugin's words
  (`error-crashed` in `core/model.ftl`).
- Renamed from `tern` to `piebird-tern-bridge`, one name for the folder, `plugin.json`,
  `package.json`, the catalog and the Tern plugin (formerly `omp-bridge`): install it as
  `piebird-tern-bridge@piebird`. The look moved to its own plugin, `piebird-tern-ghostty-style`.
- Skill `tern`: common calls for listing the window's panes, splitting a pane and running a
  command in it without taking focus, typing into a shell pane, opening a file in a new tab,
  closing a pane and naming a tab; and two notes: `cx` and its parts are userdata that `pairs`
  can't list, and Luau here has no `os.getenv`, so pane ids (numbers: yours read with
  `echo $TERN_PANE` first) and paths go into the code. Before, a small model guessed at these APIs
  and failed three calls in a row; with them it does the demo's tasks with no failed call.
- Tern agents are any coding agent in a pane, omp unless the user names another such as Claude
  Code or Codex, in the Tern part of the system prompt and the skill `tern`; the skill says how to
  start each (`command = "claude"`, `"codex"`) and how to read the reply of an agent other than omp.

### Fixed

- omp gets `tern_lua` with `strict: false`, so a GPT model sends only the arguments it uses
  rather than a value for each; `timeout_s: null` counts as left out.
- The Tern part's wake reader (a `cat` on the window's wake pipe) no longer outlives its window:
  it stops within 5 seconds after Tern quits or crashes, and a plugin reload ends the old
  window's reader at once. Before, every quit and every reload (each upgrade reloads Tern's
  plugins) left one blocked `cat` behind for good.
