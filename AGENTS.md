# piebird plugins

Plugins for omp (main lane), Claude Code, Codex and Tern. This is a public repo: write everything
for any user, with no project, client, host or person names and no personal paths.

## Layout

- `plugins/<name>/`: one installable package doing one job, named `<app>-<what it does>` (one
  name everywhere: folder, `plugin.json`, `package.json`, catalog, Tern id), with its
  `plugin.json`, `CHANGELOG.md` and `README.md`.
- `plugins/piebird-kagi-search/`: Kagi web search: the Kagi tools and the "search" setting in
  `core/`, shells for omp (`src/`), Claude Code (`com.anthropic.claudecode/`) and Codex and the
  desktop apps (`program/`; its Codex hook in `com.openai/`, in development), the `kagi` skill,
  and its vault `kagi-vault` (`cmd/kagi-vault/`), which keeps the Kagi session and talks to Kagi.
- `plugins/piebird-agent-variants/`: the `agent_variant_setup` tool.
- `plugins/piebird-sessions/`: the `session_read` tool (reads omp session journals, streamed)
  and the line, shown in the chat, naming the agent's own session.
- `plugins/piebird-tern-bridge/`: the `tern_lua` tool, the `tern` skill and, inside Tern, a part of
  every agent's system prompt; `so.stencil.tern/` is its Tern half.
- `plugins/piebird-threads/`: the open-threads list (from the folder its `folder` setting or a
  project's `.omp/threads.json` names) for omp and Claude Code, its rule and the `threads`
  skill.
- `plugins/piebird-workflow-rules/`: rules and the `failure-classes` skill on how to work, the rules
  in Claude Code through its mod.
- `plugins/piebird-tern-ghostty-style/`: the look, a Tern plugin of style sheets in `so.stencil.tern/`.
- A plugin with the `tern` host keeps its Tern plugin in `so.stencil.tern/` (the Agent Plugins
  extension directory for Tern's namespace) and needs the `omp` host: its omp part installs the
  Tern plugin with `kit/omp/tern-part.ts` (the kit, below).
- A plugin with the `claude` host may keep a mod (code that runs inside Claude Code) in
  `com.anthropic.claudecode/` (the Agent Plugins extension directory for Claude Code's
  namespace), with `hooks/hooks.json` there naming the module; the build points the generated
  Claude Code manifest at it. Its tests run with `claude plugin test com.anthropic.claudecode`.
- `catalog.json`: the plugin list and hosts; the build generates the manifests from it.
- `CHANGELOG.md`: this repo's own changes (tooling, catalog, docs, CI), in monthly sections.
- `demos/<name>/`: each plugin's demo, and `demos/<name>/<feature>/` its feature demos:
  `scenario.ts` (what happens on screen), the video (`demo.mp4`, and `demo.webp` for its README)
  and `report.md` (what the agent did for each prompt). `demos/shop-api.ts` is the made-up project
  they work in; `tools/demo/` records them ([Demos](docs/demos.md)).
- `cmd/<program>/`: a plugin's vault, Go `package main`, named by its catalog entry (`program`):
  the signed program that keeps the plugin's secrets and performs the operations that need them
  (`core/operations.json`, `vault: true`), with its golden replies (`testdata/`) and the
  generated copy of the plugin's settings it embeds.
- `internal/`: the Go packages the vaults share (secret stores, operations over JSON, local pages
  and the sign-in page, templates for people) and each vault's service client (`internal/kagi`),
  in one module, `go.mod` (`piebird.dev/plugins`).
- `tools/`: the build, its schemas, `native.ts` (compiles the programs into each plugin's
  `native/`), the changelog checks, the reference sync, and `model-page.ts`, which writes
  `docs/model/`: what the model sees from each plugin, from its scripted session
  (`plugins/<name>/test/scenario.ts`) in each harness, run through its real shells
  (`tools/model-page/`).
- `kit/`: code plugins share, with its tests, by shell: `core/` (pure), `bun/`, `omp/`, `claude/`,
  `program/` ([The kit](docs/kit.md)). A plugin can't import from outside its folder, so the build
  copies each part into `plugins/<name>/kit/` of the plugins with that shell (`src/`,
  `com.anthropic.claudecode/`, `program/`; `bun/` with `src/` or `program/`), and `core/` with
  any of them; the copies are generated, so edit `kit/`.
- `installer/`: the desktop installer for ChatGPT, Claude and the agents found beside them, one
  program per platform with every plugin built in; `core/` is what it writes into each agent's
  files (pure), `steps/` each agent's install and removal, `page.ts` and `server.ts` its page
  ([The desktop installer](docs/installer.md)). `tools/installer.ts` builds it.
- `reference/`: generated upstream material; never hand-edit. The public repo carries only
  `agent-plugins/` (its pin is in its `NOTICE.md`); the Tern material, omp's source, the Claude
  Code and Codex docs, the MCP repository and `SYNCED.md` are not in the public repo: fetch them
  with `bun tools/sync-references.ts` ([Reference material](docs/reference.md)).
- `.github/workflows/check.yml`: this repo's CI: `bun run check`, in the dev shell.

## Commands

Run in the dev shell (`nix develop`):

    bun run check         # generated files, lint, fmt:check, typecheck, tests (TypeScript and Go)
    bun run build         # regenerate manifests, the native programs (native/) and docs/model/
    bun run lint          # oxlint and golangci-lint; Luau: `selene plugins`, `stylua --check plugins`
    bun run fmt           # oxfmt and Go's formatters; `bun run fmt:check` only checks
    bun tools/sync-references.ts [tern | omp | agent-plugins | claude-code | codex | mcp ...]   # refresh reference/
    bun tools/demo/vm/run.ts <demo>... [--no-video]   # record demos in the demo machine (docs/demos.md)
    bun tools/installer.ts [--platform macos-arm64 | macos-x64 | windows-x64]   # the desktop installer, into dist/installer/

## Workflow

- Run `bun run check` before committing.
- Conventional Commits for commits and pull request titles, scoped by plugin or folder
  (`fix(piebird-sessions): …`); branches `feat/`, `fix/`, `hotfix/` or `chore/<slug>`.
- A commit changing a plugin adds an entry under its `## [Unreleased]`, and one changing
  anything else here an entry in `CHANGELOG.md`; or its message ends with the trailer
  `Changelog: none`. `CHANGELOG.md` is never released: the first change in a new month first
  runs `bun tools/changelog-cut.ts CHANGELOG.md`, which moves the earlier month's entries into
  their `## [YYYY.MM] - YYYY-MM-DD` section.
- For Tern work, check `reference/` first and cite the file; fetch it with
  `bun tools/sync-references.ts tern` when it is missing, and refresh it when the Tern section of
  `reference/SYNCED.md` is over 7 days old or its version differs from `tern --version`.
- For omp work, check omp's source in `reference/omp/` first and cite the file; fetch it with
  `bun tools/sync-references.ts omp` when it is missing, and refresh it when the omp version in
  `reference/SYNCED.md` differs from `omp --version`.
- For Claude Code or Codex work (their plugins, hooks, mods, MCP setup, config), check their
  docs in `reference/claude-code-docs/` or `reference/codex-docs/` first and cite the page; fetch
  them with `bun tools/sync-references.ts claude-code` or `codex` when missing, and refresh them
  when their section of `reference/SYNCED.md` is over 7 days old or its version differs from
  `claude --version` or `codex --version`.
- For MCP work, check the specification and schema in `reference/mcp/` first and cite the file;
  fetch it with `bun tools/sync-references.ts mcp` when missing, and refresh it when the MCP
  section of `reference/SYNCED.md` is over 7 days old.
- A pull request that adds or changes what a plugin does includes its demo video: adjust
  `demos/<plugin>/scenario.ts` when the change shows on screen, record it again, and post the
  video in a comment on the pull request yourself: `gh pr comment <pr> --body-file <file>
  --attach <demo.mp4>`, with `![](<demo.mp4>)` alone on its line in the body, so GitHub shows a
  player. Videos never go into git. A plugin whose catalog hosts list several agents shows each of
  them doing the same task: omp and Claude Code on Claude Haiku 5.5, Codex on gpt-6.1-sol. Its
  `report.md` shows no failed tool calls and no detours: an agent that stumbles means the plugin
  explains itself badly, so fix the skill, rule, tool description or error text, not the prompt.

## Conventions

- Size is a guideline, not a limit: files around 300 lines, functions around 60 (tests 400 and
  120). Split at a seam, never just to get under a number. Favor a functional core (pure logic,
  tested on its own) inside an imperative shell (I/O, processes, the network).
- When a lint rule fires, decide whether it found a real problem: fix it if so; if not, turn the
  rule off for that line with the reason, or for a whole kind of file in the linter's config
  with a comment. Never reshape correct code just to satisfy a rule.
- Each manifest has one hand-written source; never edit generated files. Run `bun run build`.
- No symlinks in plugin sources; fixed names (`plugin.json`, `SKILL.md`, ...) match exactly.
- A plugin is named `piebird-<its job>` (`piebird-sessions`, `piebird-kagi-search`), with no
  harness in the name, and that one name is its folder, `plugin.json`, `package.json`, catalog
  entry and Tern id. The prefix keeps it apart from other marketplaces' plugins where a harness
  names things by plugin alone (omp's `node_modules`, Claude Code's tool names).
- Paths here are relative to this repo's root (`plugins/piebird-sessions`, not a workspace path).
- Workflow rules stay general: a lesson from one project goes in that project's AGENTS.md.
- Every plugin whose tools reach a service has a raw mode, so agents can script around its
  tools' limits:
  - every tool takes `format`: `markdown` (the default) or `json`, which answers with the tool's
    data as JSON;
  - two tools pass a request to the service as it is: `<prefix>_raw_read` for plain reads
    (marked read-only) and `<prefix>_raw_write` for anything else, which may change the person's
    account. Each takes one `request` in the service's own form (for an HTTP service a path, or a
    request with its method, header lines and body), so the schema is the same in every plugin.
    A body over 32 KB goes to a file in the person's cache folder, kept a day; the agent gets the
    path, the size and how the body starts.

  The vault's `call <operation>` takes the same inputs, and the plugin's skill says how to use it
  when the tools fail.
- What a person sets for a plugin is declared in one place, its `core/settings.json`
  ([Settings](docs/manifests.md#settings)): settings, each a choice, text or path, and secrets,
  each with the environment variable that may supply it. The shells resolve the settings from
  the settings files and the agent's own settings screen, which the build writes from them; the
  vault keeps the secrets. Never an environment variable as a switch, and none read outside that
  file's declarations. A host part not ready for people stays under the catalog entry's
  `development`.
- Text the model receives (tool and argument descriptions, answers, messages and errors a tool
  returns, instructions, refusals) lives in one place per plugin, its `core/model.ftl`, a Fluent
  catalog ([The kit](docs/kit.md)): only its `Catalog` makes `ModelText`, the one type the shells
  send to a model, and a variable a message lacks fails. Rules and skills stay Markdown files, as
  the harnesses read them. Text only people read (command-line output, local pages, notices,
  settings labels) isn't held to this: a vault keeps its words for people in its `templates/`,
  loaded with `internal/text` (Go's `text/template`, which fails on a missing field or key, with
  the frontmatter read as YAML); its errors reach the model as ids with values, which the
  plugin's catalog words.
- Text an agent gets always costs every session, so it goes in always only when all three hold:
  the agent can't tell by itself when to look it up (a judgement or a reflex, not an event),
  missing it causes a mistake nobody notices at once, and it is short. Anything else is a skill
  or a rule read on demand, whose description states the duty itself. An always-applied rule is
  named for whom it is, `rules/<plugin>.md` (every agent) or `rules/<plugin>-<agent>.md` (its
  `agents`), and grows by sections, not files beside it; a rule read on demand is one file per
  topic. Text that matters only in some setting (inside Tern) comes from the plugin's code there,
  not `rules/`. The build refuses a misnamed always-applied rule, and an agent whose always-on
  rules from one plugin pass 1,500 tokens (`tools/build/rules.ts`).
- Every plugin that sends the model anything (a catalog, operations, rules or skills) has a
  scripted session, `test/scenario.ts`, run through its real shells by `tools/model-page.ts` into
  its `docs/model/` page: each text in each harness with the messages it is made of, then the
  skills and rules it ships. Review a page's diff with the catalog's; `bun run build` writes it,
  and `bun run check` fails on a page out of date or a plugin with model text and no session.
  - A vault's golden files are its replies to each call in `testdata/calls.json` against a fake
    of its service serving captured pages, in `testdata/replies/`, compared on every `go test` and
    rewritten by `go test ./cmd/<program> -run Golden -update`. The plugin's tests check each
    against `core/operations.json` and turn it into the model's text; its scenario's stand-in
    vault answers with them.

## Code Review Rules

- Schemas are the authority for `plugin.json`, `mcp.json`, the catalog and skill frontmatter.
  Safe path: put a new structural rule in the schema; hand-check only spec prose, citing it.
- A generated file's shape follows its consumer's docs, tested with the consumer's own CLI.
  Safe path: extend `tools/build/consumers.test.ts`, not a copy of the consumer's rules.
- Path containment is lexical, through `isOutside` in `tools/build/paths.ts`.
  Safe path: call `isOutside`; don't add symlink resolution (links are rejected first).
- omp installs no packages for a marketplace plugin: an omp extension imports by name only
  `@oh-my-pi/`, `node:` and Bun's own modules (`ompImportProblems` in `tools/build/purity.ts`).
  Safe path: declare a library in the plugin's `vendor.json`; the build copies it into `vendor/`.

## More detail

- [Manifests and the build](docs/manifests.md) · [Reference material](docs/reference.md) ·
  [Security](docs/security.md)
