# piebird

Plugins for coding agents: [omp](https://github.com/can1357/oh-my-pi) first, Claude Code and
Codex where a plugin works there too, and the [Tern](https://docs.stencil.so/tern/) terminal.

Each plugin's README shows it working in a short video.

| Plugin | What it gives you | Works in |
| --- | --- | --- |
| [piebird-kagi-search](plugins/piebird-kagi-search/README.md) | Kagi web search, quick answers and Kagi News with your own Kagi account, from the plugin's own program; the `kagi` skill; a setting for how much the agent relies on Kagi over its own web search | omp, Claude Code, Codex, ChatGPT, Claude |
| [piebird-agent-variants](plugins/piebird-agent-variants/README.md) | The `agent_variant_setup` tool: temporary project-scoped variants of an agent, with explicit model routing | omp |
| [piebird-sessions](plugins/piebird-sessions/README.md) | The `session_read` tool: reads, pages and searches a session journal (omp's, Claude Code's or Codex's) by session id and line without opening it whole, with asks shown in full (each question, its options and what was picked or typed); and a line telling the agent its own session id | omp, Claude Code, Codex, ChatGPT, Claude |
| [piebird-tern-bridge](plugins/piebird-tern-bridge/README.md) | The `tern_lua` tool, running Lua with Tern's window API in the Tern window holding omp's pane, and the `tern` skill | omp in Tern |
| [piebird-threads](plugins/piebird-threads/README.md) | Your project's open threads in front of the agent: the files in the folder its settings name, in omp before a prompt whenever the list changes and shown in the chat, in Claude Code at the start of a conversation; a rule pointing to the `threads` skill, which gives the few parts of a thread file the list reads and leaves the rest to the agent | omp, Claude Code, Codex, ChatGPT |
| [piebird-workflow-rules](plugins/piebird-workflow-rules/README.md) | Rules on how to work (proportion, thinking before building, fixing corrections as classes, project tooling, changelogs, asking for decisions, messages that stand alone, weighing advice) and the `failure-classes` skill | omp, Claude Code, Codex, ChatGPT |
| [piebird-tern-ghostty-style](plugins/piebird-tern-ghostty-style/README.md) | omp's chat in Tern drawn the way omp looks in Ghostty: one box per tool call, thoughts left open, bash as `$ command`, compact diffs and replies | omp in Tern |

## Install

On a Mac or a Windows PC with ChatGPT or Claude, download the installer from the releases page
(`piebird-<version>-macos-arm64.dmg` for Apple silicon, `-macos-x64.dmg` for an Intel Mac,
`-windows-x64.exe` for Windows) and open it. It lists the plugins and the apps on your computer
they go to; pick the plugins and click Install. It finds omp, Claude Code and Codex too.
[docs/installer.md](docs/installer.md) has what it writes where.

In a terminal, add this repository as a marketplace once, then install the plugins you want.
piebird-kagi-search needs its vault, a program a marketplace can't carry, so it comes with the
installer.

omp:

    omp plugin marketplace add georgelubaretsi/piebird
    omp plugin install piebird-sessions@piebird

Claude Code:

    claude plugin marketplace add georgelubaretsi/piebird
    claude plugin install piebird-threads@piebird

Codex:

    codex plugin marketplace add georgelubaretsi/piebird
    codex plugin add piebird-threads@piebird

Codex runs a plugin's program (piebird-kagi-search's, piebird-sessions') only as the installer
sets it up, so those two come to Codex through the installer.

A plugin that works in Tern carries a Tern plugin too (its `so.stencil.tern/` folder), and omp
brings it along: when omp starts in a Tern pane, it installs that Tern plugin if Tern lacks it,
updates it after `omp plugin upgrade`, and says so in the chat. There is nothing to install in
Tern yourself. A Tern plugin turned off in Tern's settings is left alone.

## Contributing

Issues and pull requests are welcome. This repository is exported from a private workspace, so a
pull request is applied there by hand, with credit to its author, and arrives here as a new
commit rather than as a merge.

## Development

Everything runs in the dev shell ([Nix](https://nixos.org/download/)):

    nix develop
    bun install
    bun run check                  # generated files, lint, format, typecheck, tests

[AGENTS.md](AGENTS.md) has the layout, commands and conventions. Tern's docs are not
redistributed here; `bun tools/sync-references.ts tern` fetches them into `reference/`.

## License

[MIT](LICENSE). `reference/agent-plugins/` is the Agent Plugins specification and schemas,
redistributed under their own licenses ([NOTICE](reference/agent-plugins/NOTICE.md)).
