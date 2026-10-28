# Changelog

All notable changes to this repository's own tooling, catalog, documentation and CI are
documented in this file. Each plugin under `plugins/` keeps its own changelog.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/2.0.0/).
This repository is never released as a whole: entries collect under Unreleased, and the first
change in a new month moves them into a section for the month they were last changed in,
`## [YYYY.MM] - YYYY-MM-DD`, dated its last day (`bun tools/changelog-cut.ts CHANGELOG.md`).

## [Unreleased]

### Added

- Rules are written for what they cost (AGENTS.md, Conventions): text goes in always only when the
  agent can't tell by itself when to look it up, missing it goes unnoticed, and it is short. The
  build refuses an always-applied rule not named for whom it is (`rules/<plugin>.md` for every
  agent, `rules/<plugin>-<agent>.md` for one) and an agent whose always-on rules from one plugin
  pass about 1,500 tokens (`tools/build/rules.ts`). The model pages say whose system prompt each
  always-applied rule is in.
- The desktop installer (`installer/`, `docs/installer.md`): one program per platform, a disk
  image with "Install piebird.app" for macOS and an .exe for Windows, with every plugin built in.
  It finds ChatGPT, Claude, Claude Code, Codex and omp, opens a page in the browser listing the
  plugins and where each goes, and installs or removes them with one click: omp and Claude Code
  from one shared copy in `~/.agents/piebird/marketplace/`, ChatGPT and Codex through Codex's own
  plugin command (or its files, as that command writes them), Claude chat with a .mcpb per plugin
  with a program, opened with Claude. The page then offers restarting ChatGPT, signing in and the
  settings page. `bun tools/installer.ts` builds it; the tag `installer/v<version>` releases it.
- Desktop demos in a throwaway macOS virtual machine (`tools/demo/vm/`, `just demo-desktop
  <demo>`, docs/demos.md): tart clones a base image, the scenario installs the apps there, and
  one VNC connection watches and drives the screen into the same video format as the plugins'
  demos. `demos/installer-macos/` records the installer in dark mode (the setting written, then
  the login session restarted): open it, install, add a plugin to Claude chat, choose a setting.
  With `DEMO_SHOTS` set, a failed run saves the screen it ended on.
- omp and Tern demos record in the demo machine (`tools/demo/vm/run.ts`, docs/demos.md,
  "Recording in a virtual machine"): a throwaway clone of a macOS image Packer builds
  (`machine.pkr.hcl`, dark, with Tern, Nix, omp and the flake's `demo-machine` tools), where the
  recorder sets omp and Tern up as a person does: the desktop installer's marketplace added and
  the plugins installed from it, Kagi signed in with the vault's own sign-in. omp's models come
  from this Mac's `omp auth-gateway` through the SSH connection, so no credential goes in; Tern's
  sign-in sheet is hidden, nothing signed in. Demos with Claude Code and Codex still record on
  this Mac (`tools/demo/place-host.ts`).
- The demos of piebird-sessions, piebird-threads, piebird-workflow-rules and piebird-kagi-search
  show each agent the plugin works in, a tab each (omp, Claude Code, Codex); every demo was
  recorded again on the new plugins. Codex in a demo gets the plugins as the desktop installer
  gives them; Claude Code may call the plugins' tools without asking; its trust question is
  answered from what it shows. Tern draws its window itself, so this Mac can be locked meanwhile.
- A demo recorded on this Mac gets Kagi's session (`KAGI_SESSION_TOKEN`, or the kagi CLI's) as
  `KAGI_SESSION_TOKEN` for its agents, and Codex's copy of the plugin sets it in its `mcp.json`,
  since Codex passes a plugin's program none of its own variables: nothing goes into this Mac's
  Keychain (`tools/demo/credentials.ts`).
- A demo recorded on this Mac whose window shows the login name (an agent listing files prints
  their owner) gets no video, and the recorder exits 1: it reads the recording twice a second
  with tesseract, now in the dev shell (`tools/demo/onscreen.ts`).
- The kit's settings page (`kit/program/settings.ts`): a plugin's program opens the person's
  settings in their browser with `settings` and saves them into `~/.agents/piebird/settings.json`,
  keeping what else the file holds; a local page on 127.0.0.1 behind a random path, as the
  vaults' sign-in page is, refusing other host names.
- `docs/security.md`: what the plugins protect when they run, who holds a secret (only a
  service's vault, never plugin code in the agent or the Bun program), the vault's guards, where
  the session is kept on each system, and what is out of scope.
- This changelog, for the repository's own tooling, catalog, documentation and CI, with a section
  per month. `bun tools/changelog-cut.ts <file>...` closes a month: once it is over, the entries
  the last commit has under Unreleased move into `## [YYYY.MM] - YYYY-MM-DD`, dated the month's
  last day; entries added since stay under Unreleased. `bun tools/check-changelog.ts` accepts
  month sections, dated within their month, only in this changelog.
  `tools/check-changelog-entries.ts` asks for an entry here for a change outside a plugin's
  folder, and refuses a new entry while Unreleased still holds an earlier month's.
- Linting and formatting with size and complexity limits: oxlint (type-aware) and oxfmt for
  TypeScript, pinned in `package.json` (`bun run lint`, `bun run fmt`), and selene and StyLua for
  Luau. The dev shell provides the tools.
- Changelog checks. `bun tools/check-changelog.ts <file>...` checks that each changelog is named
  exactly CHANGELOG.md and is in Keep a Changelog format, with one Unreleased section and a date
  on every release, as the `keep-a-changelog` parser reads the headings. The build requires each
  plugin to keep one whose newest release has its `plugin.json` version.
  `tools/check-changelog-entries.ts` checks that a commit adds an entry under `## [Unreleased]`
  in the changelog of each thing it changes, unless its message ends with the trailer
  `Changelog: none`, which waives the entry but not the changelog.
- Plugins that hold a secret ship a vault: a Go program that keeps the secret and performs the
  operations that need it (`core/operations.json`, `vault: true`), a command in
  `cmd/<program>/` that the plugin's catalog entry names (`program`), in one module for all
  (`go.mod`, `piebird.dev/plugins`), built by `bun tools/native.ts` (part of `bun run build`)
  for macOS and Linux (arm64 and x64) and Windows (x64) into the plugin's gitignored `native/`
  folder, reproducibly, with a starter script that runs the build for the computer it is on.
  `internal/` holds the parts they share: operations over JSON on stdin and stdout, each error a
  declared id with values the plugin's catalog words (`ops`), the secret stores (`secrets`),
  templates for the words people read (`text`), long bodies kept as files (`results`), pages on
  127.0.0.1 (`localpage`) for signing in (`signin`) and the installed Chrome's request headers
  (`chrome`). A vault's golden replies (`testdata/replies/`, `go test ./cmd/<program> -run
  Golden -update`) are its answers to each call in `testdata/calls.json` against a fake of its
  service; the plugin's tests check them against `core/operations.json`, and a Go test checks
  that the vault performs exactly the operations given to it there. `bun run check` lints and
  formats them with golangci-lint (`.golangci.yml`) and runs their tests with the race detector;
  the dev shell has `go` and `golangci-lint`.
- Settings, one system for every plugin: everything a person sets for it is declared in the
  plugin's `core/settings.json` (`tools/settings.schema.json`): settings and secrets, each
  secret with the environment variable that may supply it. The vault keeps the secrets in the
  system's secret store (the macOS Keychain, Windows Credential Manager, the Secret Service on
  Linux, else a file only the person can read). The build gives each agent its own settings
  screen from the same file: `userConfig` for Claude Code, which its mod gets, and
  `omp.settings` for omp. An agent's own choice wins there; its default, `shared`, follows the
  settings files, which every agent reads. CI tests each secret store on its own system
  (`vaults` in `.github/workflows/check.yml`): the Keychain on macOS, Credential Manager on
  Windows, and GNOME Keyring's Secret Service on Linux.
- Settings can be a text or a path beside a choice, and live in two files of one format: the
  person's `~/.agents/piebird/settings.json` and the repo's `<project>/.agents/piebird/settings.json`,
  a section per plugin. `kit/core/settings.ts` resolves each setting: the plugin's default, then
  the project's file, then the person's, then the agent's own screen; a value that isn't
  declared, is a secret or isn't a choice is reported and skipped. `core/settings.gen.ts` gives
  the shells the declarations, and `schemas/settings.schema.json` gives editors the files' shape.
  Each plugin reads the files once it moves to the kit.
- A README (the plugins, how to install them in each agent and in Tern, contributing,
  development) and the MIT license. `reference/agent-plugins/` carries the Agent Plugins license
  texts (Apache-2.0 for the schemas, CC-BY-4.0 for the spec) and a `NOTICE.md` saying what came
  from where; `bun tools/sync-references.ts agent-plugins` fetches and writes them on every
  refresh.
- `bun run fmt` and `bun run fmt:check` format CSS too, with oxfmt and the same settings as
  TypeScript.
- The README says how to install the tern plugin's `omp-ghostty` look in Tern, that it needs
  Tern 0.7.1 or later, and the one thing it changes outside omp (a wider column for rendered
  Markdown in file panes); `docs/reference.md` says to recheck its style sheets after a Tern update.
- The catalog lists the sessions plugin (the `session_read` tool and the agent's own session
  line) and the threads plugin (the open-threads list from the folder a project's
  `.omp/threads.json` names, its rule and skill), both for omp; the README describes them, with
  both messages shown in the chat.
- AGENTS.md: the text the model receives lives in one place per plugin, its `core/model.ftl`, so
  a review shows what is passed to the model, and every plugin that sends the model anything has
  a scripted session behind its page in `docs/model/`. A vault keeps its words for people in
  `templates/`, filled with Go's `text/template` through `internal/text`; the tools' words for
  people (notices, descriptions, the demo report) are written in their code.
- AGENTS.md: every plugin whose tools reach a service has a raw mode: `format: json` on every
  tool, and a `<prefix>_raw_read` / `<prefix>_raw_write` pair that passes a request to the
  service as it is, a long body saved as a file.
- `bun tools/sync-references.ts omp` keeps omp's source in `reference/omp/`: a shallow git clone
  of can1357/oh-my-pi at the tag of the installed omp (`omp --version`), refreshed in place when
  the version changes, ignored by git and not in the public repo. `SYNCED.md` gets an omp section;
  `docs/reference.md` and AGENTS.md say where its extension API, session journal and renderers
  are, and to check it before guessing at omp.
- Tern is a catalog host. Tern has no marketplace, so a plugin with the `tern` host also needs
  the `omp` host (the catalog schema), keeps its Tern plugin in `so.stencil.tern/` (the Agent
  Plugins extension directory for Tern's namespace), and its omp part installs it with
  `src/tern-part.ts`. The build checks that the folder exists exactly when the catalog lists
  `tern`, and that its `plugin.toml` has the plugin's name as `id` and `plugin.json`'s version;
  the consumer tests link it with Tern itself.
- The kit: code plugins share, kept once in `kit/` with its tests and split by shell (`core/`,
  `omp/`, `claude/`, `program/`). A plugin can't import from outside its folder, so the build
  copies each part into `plugins/<name>/kit/` of the plugins with that shell, and `core/` with
  any of them (tests stay in `kit/`). `bun tools/build.ts --check` fails on a copy that differs
  from its source, and the build deletes one a plugin no longer needs. `kit/omp/` holds the
  code that installs a Tern part; `kit/core/model.ts` the strict Fluent catalog (`Catalog`,
  `ModelText`). Libraries the kit carries are declared in `kit/vendor.json`, and those one
  plugin carries in its own `vendor.json`; the build copies them from their pinned packages into
  `vendor/` folders (`kit/<part>/vendor/`, `plugins/<name>/vendor/`), with their license
  (`@fluent/bundle`, Apache-2.0; piebird-agent-variants' `yaml`, ISC); lint and format leave them
  alone. A declaration whose source leaves its package, or whose copy isn't a folder under a
  `vendor/` folder, is refused. omp installs no packages for a marketplace plugin, so the build
  refuses an omp extension (a plugin's `src/` and the kit parts it gets, in any script Bun loads:
  `.ts`, `.tsx`, `.mts`, `.cts` and their JavaScript kin) importing a package by name other than
  what omp provides: `@oh-my-pi/`, `node:` and Bun's own; type-only imports are fine.
- A plugin's model text lives in `core/model.ftl`, one Fluent catalog. The build turns it into
  `core/model.gen.ts`: the catalog embedded as text (a Claude Code mod imports only code) and a
  type naming every message and the variables it needs, references followed, so a wrong id or
  a missing variable fails to compile. The build refuses an entry the runtime parser would
  skip, an id defined twice and a reference to a message that isn't there.
- Core stays pure: in a plugin's `core/` and in `kit/core/`, oxlint refuses imports that aren't
  relative, runtime and I/O globals, `Date.now` and `Math.random`, and the build refuses a
  relative import that leads out of core to a shell or another plugin.
- A plugin declares what it can do in `core/operations.json` (`tools/operations.schema.json`):
  each operation's input and output as JSON Schema, its errors, whether its vault performs it
  and whether the model gets it as a tool. Text the model reads stays in `core/model.ftl`: the
  build refuses text keywords in the schemas, and a tool, argument or error the catalog doesn't
  describe. It generates `core/operations.gen.ts`, the operations with their text, for the shells.
- Shell kits ([The kit](docs/kit.md)): `kit/omp/` registers a plugin's operations as omp tools,
  each call performed by the handlers made for the calling session's context, and reads omp's own
  settings choices, each tool approved as omp approves a read (read-only), code execution (`runsCode`, a
  tool that runs code the model wrote) or a change (any other), its handlers given the call's
  abort signal;
  `kit/claude/` does the same in a Claude Code mod, with the `ioOf($)` each
  hooks module carries and the part of Claude Code's mod API it uses declared in
  `claude-code.d.ts`, with the part of `claude-code/testing` a mod's tests use in Claude Code's
  engine; `kit/program/` is a Bun program's MCP server (for clients of the 2025
  handshake and of the 2026-07-28 protocol), which tells the program of each call's outcome with
  the call's `_meta` (`afterCall`), Codex hook answers and `call <operation>`; a compiled program
  finds its plugin's folder from `native/<platform>/`, or `native/` on Windows. An MCP
  result is the outcome's text only, as the model reads it in the other shells: Codex shows a
  result's structured content instead of its text. `kit/core/` adds `Io` (reading a file whole or
  in pieces, for files too big to hold, which a mod reads through `cat`, or `type` on Windows,
  past `$.fs.read`'s 4 MiB), the operation contract, the vault protocol and where a plugin's vault
  is (`vaultPath`); a `Catalog` words a message whose id arrives at run time, such as a vault's
  error, with the same refusals (`textById`); `rules.ts` reads a rule the plugin ships as omp
  does, for a harness with no rules of its own. Numbers in model text
  are written without the locale's grouping (line 1234, not 1,234). New dependency
  `@modelcontextprotocol/server` 2.2.0, pinned, with `@modelcontextprotocol/core` 2.2.0 and `zod`
  4.6.5; no install scripts.
- "What the model sees" pages: `bun tools/model-page.ts` (part of `just build`; `just check`
  compares) runs each plugin's scripted session (`plugins/<name>/test/scenario.ts`) through each
  of its shells, the omp extension, the Claude Code mod and the program as Codex runs it, in a
  made-up home folder, and writes `docs/model/<name>.md`: every text the model gets at each step,
  in full, once for the harnesses that got the same, with the `model.ftl` messages it is made of,
  then the skills and rules the plugin ships, as the harnesses read them; and
  `docs/model/index.md`, every plugin with its page. It fails for a plugin that sends the model
  text (a catalog, operations, rules or skills) without a scripted session. A scenario may make
  its own copy of the plugin's folder, with stand-ins for its native programs
  (piebird-kagi-search's answers with the vault's golden replies), and may run at a fixed time;
  every session runs in UTC, with git's own configuration out of the way.
- The build refuses a Claude Code mod whose hooks module carries a copy of the kit's `ioOf($)`
  that differs from `kit/claude/io-of.md`'s.
- Bun programs: `bun tools/native.ts` compiles a plugin's `program/main.ts` for each platform
  beside its Go programs, reading no `bunfig.toml`, `.env`, `tsconfig.json` or `package.json`
  where it runs, and signs the macOS builds again on a Mac (ad hoc, or with
  `PIEBIRD_CODESIGN_IDENTITY`). `--release` refuses a build linking a library outside the
  system's, as programs from a Bun that isn't Bun's official build do.
- Releases: pushing `<plugin>/v<version>` builds the plugin's native programs into a draft
  GitHub release (`.github/workflows/release.yml`, `tools/release.ts`): built on a Mac with Bun's
  official build, unsigned, with build provenance attestations, one archive per platform with
  `SHA256SUMS`. The workflow holds no secrets; a release is signed before it is published.
- Supply chain: Bun installs a version only once it has been public for 14 days
  (`bunfig.toml`; omp's packages exempt, as they track the harness), no dependency's install
  scripts run (`"trustedDependencies": []`), every dependency is pinned exactly so security
  fixes pass the wait, and `bun run audit` checks both ecosystems (`bun audit`,
  `go tool govulncheck`). Go builds with its latest release (`toolchain go1.27.2` in `go.mod`),
  and golangci-lint comes from the same Go line.
- Host parts: a plugin may carry code that runs inside a host, in the Agent Plugins extension
  directory for that host's namespace, with its hooks file at `hooks/hooks.json` there: a Claude
  Code mod in `com.anthropic.claudecode/`, Codex command hooks in `com.openai/`. The build names
  the file in the generated manifest for that host (`hooks` in `.claude-plugin/plugin.json`, and
  a generated `.codex-plugin/plugin.json`), so neither host reads the other's, and checks that
  each folder exists only for its host and holds the hooks file; the consumer tests read the mod
  with `claude plugin validate`. A catalog entry's `development` lists hosts whose part is built
  and tested but left out of their manifest. `.claude-plugin/types/`, which Claude Code writes
  into a plugin it loads with `--plugin-dir`, is ignored.
- Demos: every plugin has a demo video (`demos/<plugin>/demo.mp4`, and `demo.webp` for its
  README) and a report of what the agents did for each prompt (`report.md`).
  `bun tools/demo/record.ts <plugin>` records one from `demos/<plugin>/scenario.ts`: a Tern window
  with its own profile, an omp home with the plugin linked from the checkout and signed in
  through `omp auth-broker serve`, Claude Code and Codex for a plugin that works there too, and a
  made-up project (`demos/shop-api.ts`). It films the window, adds captions and speeds up the
  waits, writes a 1080×1350 MP4 for phones, and exits 1 when an agent's tool call failed
  ([Demos](docs/demos.md)). The dev shell has ffmpeg for it.
- `bun tools/sync-references.ts` has three more sources: `claude-code` and `codex` copy every
  page of code.claude.com's and learn.chatgpt.com's docs (their `llms.txt`), and `mcp` clones
  the Model Context Protocol's repository (every specification version, the schemas, the SEPs).
  AGENTS.md asks agents to check them first and refresh them when over 7 days old or when the
  installed agent's version differs. None of them is in the public repo.

### Changed

- oxlint no longer limits file and function length (`max-lines`, `max-lines-per-function`):
  AGENTS.md makes length a guideline, split at a seam rather than to get under a number. The
  complexity, depth, parameter and callback limits stay.
- AGENTS.md is short instructions for agents: layout, commands, workflow, conventions and a few
  code review rules. The detail moved to `docs/` (manifests, reference material).
- Plugins renamed: a `piebird-` prefix, no harness in the name, and one name everywhere (folder,
  `plugin.json`, `package.json`, catalog, Tern id): `piebird-kagi-search` (was `kagi`),
  `piebird-agent-variants` (`agent-variants`), `piebird-sessions` (`sessions`),
  `piebird-tern-bridge` (`tern`), `piebird-threads` (`threads`) and `piebird-workflow-rules`
  (`workflow`). The prefix keeps them apart from other marketplaces' plugins where a harness
  names things by plugin alone (omp's `node_modules`, Claude Code's tool names). The look left
  the tern plugin for its own, `piebird-tern-ghostty-style`. The README lists every plugin with
  where it works and drops the `tern plugin install` steps.
- The marketplace is named `piebird` (was `omp-drawer`), in `catalog.json`, `package.json` and
  every install command in the READMEs: plugins install as `<plugin>@piebird`. Programs keep
  their files under `piebird/<program>` in the user's config and cache folders.
- The public repo is `georgelubaretsi/piebird` (was `omp-drawer`; GitHub forwards the old name):
  the install commands in the READMEs and each plugin's `homepage` and `repository` point there.
- Every word a tool sends the model comes from its plugin's catalog, its failures too. A tool
  whose code fails answers with the catalog's `error-crashed`, with the failure's message, and
  the program's MCP server checks arguments against the tool's schema itself and answers with
  `error-arguments` instead of the SDK's words; the build refuses a plugin with tools that lacks
  either. `ModelText` carries a brand only `kit/core/model.ts` writes (the build refuses it
  anywhere else), so no other object passes for text from a catalog.
- A repo can't override the person in omp either: omp's project overrides
  (`.omp/plugin-overrides.json`) rank with the project's settings file, below the person's,
  though omp puts them over its own global settings. Claude Code reads plugin options from the
  person's settings only.
- The settings page has "Automatic" for each setting: the project's choice, else the default.
  Any value picked is kept, the default's too, so it holds over a project's choice.

### Removed

- The programs' `-agent key=value` option: no host passes a program settings of its own (the
  `.mcpb` for Claude chat has no `user_config`), so a program reads the settings files alone.

### Fixed

- The kit registers each omp tool with `strict: false` (`kit/omp/tools.ts`). Without the flag omp
  sends OpenAI the tool with no strict flag and its optional arguments not nullable, and GPT
  models filled every argument with a made-up value, which tools with exclusive arguments
  refused: every `kagi_search` and `session_read` from GPT-6.1 Sol failed. Measured with real
  calls: 6 of 6 failed without the flag, 6 of 6 worked with it.
- Every shell (omp, Claude Code, MCP, `call`) leaves out the arguments set to null before it
  checks a call or runs the handler (`withoutNulls` in `kit/core/operations.ts`), so a caller
  that sends every argument, null for those it doesn't use, gets what leaving them out gets.
- macOS builds of the Bun programs signed with the Developer ID now carry the `allow-jit`
  entitlement (`tools/bun.entitlements`). Under the hardened runtime without it, Bun's
  JavaScript engine can't compile and a program ran about 8 times slower (measured: 8.1 s
  against 1.0 s on a CPU-bound program).
- A local page (sign-in, settings) ends at once when the person is done. It used to wait 5
  seconds when the browser had opened a connection ahead of time, since net/http's `Shutdown`
  counts such a connection as idle only after 5 seconds; `Shutdown` now closes connections that
  never sent a request.
- The build accepts an MCP stdio `command` that is a `./` path with spaces when it names a
  bundled file; a bare command with whitespace is still refused as a shell string.
- `bun run test` runs the tests under `tools/` only (`bun test ./tools`). As a bare word, `tools`
  matched any test path containing it, so the test files of a source cloned into `reference/`
  ran too and failed.
- `golangci-lint fmt` leaves `reference/` alone (`.golangci.yml`). It walks every Go file under
  the module, so the lint failed on upstream code cloned there, such as the Tern SDK's examples.
