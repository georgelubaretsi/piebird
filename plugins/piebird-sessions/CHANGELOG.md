# Changelog

All notable changes to this plugin are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/2.0.0/),
and this plugin adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Tool `session_read` (read-only): reads a session journal, omp's, Claude Code's or Codex's, by
  session id, id prefix or `.jsonl` path (also starting with `~`, as the session line shows it);
  a prefix several sessions share fails, listing at most 10 of them. With a line: that entry
  and the message it answered or followed; `before` and `after` page by messages around it;
  `find` searches the session; `user` keeps only the user's words; `thinking` and `tools` add the
  agent's thinking and tool calls; `raw` returns the exact journal lines. The journal is
  streamed, never loaded whole, and closed when a read stops early. Each answer ends with the next
  call to make, or says the session ends there when nothing the flags show follows. For filtering
  it doesn't do, its description tells the agent to run jq or python over the journal file, and
  where each agent keeps its journals.
- Asks shown in full, from the question's line or the answer's: each question, its options with
  their descriptions, and what was picked or typed.
- The agent knows its own session: in omp, before a prompt, the main agent gets a line with the
  session id, its journal and the session it was forked from, again after a fork, a move or a
  compaction, shown in the chat as a `sessions.self` card; in Claude Code, the line is a block of
  the conversation's context.
- Every text the agent gets (the tool's description, its output, errors, the session line) is in
  `core/model.ftl`, a Fluent catalog: change the wording there, not in the code. A variable a
  message uses that the code doesn't give is an error, not blank text.
- Supported hosts: omp; Claude Code, as a mod with the same tool and line. The plugin's program
  (`program/`) serves the tool over MCP and answers Codex's SessionStart hook with the line, for
  Codex and the desktop apps, which get it from the installer.
- Claude Code's and Codex's journals read as omp's: their messages, thinking, tool calls with the
  results named by the call, and titles; a Claude Code side chain or meta line and a Codex event
  that repeats a response item stand for nothing, and the turns a Codex rollback undid are left
  out.
- `session_read` without a session lists this project's sessions, newest first, with each
  one's id, start, title and first prompt, and the call that reads the newest other one: the
  agent finds an earlier session without listing folders in bash. The program, which isn't told
  the project, lists every agent's sessions, each with its agent and project.
- `session_read` with a session and no line or `find` reads the session from its start, 5
  messages unless `after` gives another count: the agent asking for "the user's words" with
  `user` alone no longer gets an error first.
- README, with a demo video: a new session finds what an earlier one decided and quotes your
  words.

### Changed

- `session_read` failing in the plugin's own code, or getting arguments its schema doesn't take,
  tells the model so in the plugin's words (`error-crashed`, `error-arguments`).
- `session_read` with `find` but no session lists the sessions to pick the one to search from,
  with how to search it, rather than refusing: `find` searches one session.
- Renamed from `sessions` to `piebird-sessions`, one name for the folder, `plugin.json`,
  `package.json` and the catalog: install it as `piebird-sessions@piebird`.

### Fixed

- GPT models in omp can use `session_read`: omp gets it with `strict: false`, so a GPT model
  sends only the arguments it uses. Before, it filled every one, `find: ""` together with
  `before` and `after`, and every read was refused.
- An argument set to null counts as left out, as callers that send every argument mean it:
  `find: null` was refused as not text.
- `find` given with `before` or `after` is refused with how to fix it: leave them out to search,
  or `find` out to read a page around the line.
