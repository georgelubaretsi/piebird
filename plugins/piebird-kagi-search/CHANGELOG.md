# Changelog

All notable changes to this plugin are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/2.0.0/),
and this plugin adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Kagi search for agents, with the person's own Kagi account (no API key, no credits): the tools
  `kagi_search`, `kagi_batch_search` and `kagi_quick` (in front of the model from the first
  prompt), `kagi_news_search`, `kagi_news`, `kagi_news_categories`, `kagi_news_chaos`,
  `kagi_news_filter_presets`, `kagi_smallweb` and `kagi_auth_status`. They run inside omp
  (`src/`) and inside Claude Code, as a mod's own tools (`com.anthropic.claudecode/`), and as an
  MCP server in the plugin's program for Codex and the desktop apps (`program/`); one core
  (`core/`) holds them, the "search" setting and every word the model reads (`core/model.ftl`).
- `native/piebird-kagi-search settings` opens the "Search with Kagi" choice in your browser and
  saves it for every agent, for Codex and the desktop apps, which have no settings screen for it.
- The vault, `native/kagi-vault`: a small Go program that keeps the Kagi session and talks to
  Kagi, which the tools ask by operation name. It answers with Kagi's results, never the session,
  and nothing is downloaded at run time. On its own command line it signs in (`sign-in`,
  `sign-in --link '<Session Link>'`), signs out, says whether the session works (`status`) and
  performs an operation (`call <operation>`, the input as JSON on stdin).
  The README says who can read the session where it is kept, and links `docs/security.md`.
- Raw mode, for what the tools don't cover: every tool takes `format: json` for its data as
  JSON; `kagi_raw_read` sends a GET to any page of kagi.com (signed in) or news.kagi.com and
  returns the response as it came, and `kagi_raw_write` sends any other request, which may
  change the account. A response is never followed off Kagi, never carries the session token
  (as written or URL-encoded) nor a cookie Kagi sets; a request can't set `Cookie` or `Host`,
  and a read never reaches the sign-out page. A body over 32 KB is saved to a file in the
  person's cache folder for a day, with its size and how it starts.
- Signing in from the browser: the first search without a session opens a page on this computer
  that sends the person to Kagi's Session Link and takes it when they paste it; the search
  answers once they have, or says where the page is. The session is kept in the system's secret
  store (the macOS Keychain, Windows Credential Manager, the Secret Service on Linux, else a file
  only the person can read); `KAGI_SESSION_TOKEN` overrides it.
- Requests carry the installed Chrome's User-Agent and client hints, as a browser's would.
- Skill `kagi`: the tools, raw mode, signing in, and the vault's command as the fallback.
- Setting "Search with Kagi": how much the agent relies on Kagi. `first` (the default): it
  searches with Kagi, and its own web search stays out of the way until Kagi fails in the
  session (out of reach, a sign-in needed, a vault that doesn't answer; not a call the agent got
  wrong); `only`: Kagi alone, its own web search refused; `offered`: Kagi is one more way to
  search. The agent gets instructions to match. Choose it for every agent in
  `~/.agents/piebird/settings.json`, for a project in its `.agents/piebird/settings.json`, or
  for one agent in its own settings (omp: `omp plugin config set`; Claude Code: `/plugin
  configure`), which wins there.
- In omp, the built-in `web_search` is hidden to match the setting.
- In Claude Code (2.1.287 or later), the mod does the same for the built-in `WebSearch`: it
  waits behind tool search and a call to it is refused with a pointer to `kagi_search`; with
  `first`, it runs while the plugin has no vault built.
- For Codex, a hook (`com.openai/`, run by the plugin's program) that refuses `web.run`
  searches to match the setting. Codex doesn't run the hooks of plugins in this format yet, so
  the build leaves it out of the Codex manifest for now.
- [What the model sees](../../docs/model/piebird-kagi-search.md): every text the model gets from
  the plugin, in omp, Claude Code and Codex, from the vault's replies to pages captured from Kagi.
- README, with a demo video: omp, Claude Code and Codex each answer a question about this week's
  software with Kagi search.

### Changed

- A tool that fails in the plugin's own code, or gets arguments its schema doesn't take, tells
  the model so in the plugin's words (`error-crashed`, `error-arguments` in `core/model.ftl`).
- In omp, a project's `.omp/plugin-overrides.json` no longer overrides your own choice of "Search
  with Kagi": it ranks with the project's settings file, below yours.
- The program no longer takes `-agent search=<choice>`: it reads the settings files.
- `kagi_news` names its common categories (World, Technology, Science, Business, Sports), so an
  agent asks for one without listing them first.
- Renamed from `kagi` to `piebird-kagi-search`, one name for the folder, `plugin.json`,
  `package.json` and the catalog: install it as `piebird-kagi-search@piebird`. omp and Claude
  Code name its tools after the plugin, so their names change with it.
- The README installs it with the piebird installer, which brings its vault: `omp plugin install`
  and `claude plugin install` get the plugin without one, since a marketplace carries only the
  repository's files.

### Fixed

- A search Kagi sends to another site, as it does a query with a bang such as `osu!`, no longer
  counts as a sign-out. It said Kagi had signed the session out and opened the sign-in page in
  your browser, and in `kagi_batch_search` it failed every query. Now the tool says where Kagi
  sent it and to leave the `!` out. A 403 for one request isn't a sign-out either: only Kagi's
  home page refusing the session is.
- GPT models in omp can search with Kagi: omp gets the tools with `strict: false`, so a GPT model
  sends only the arguments it uses. Before, it filled every one, `time` together with
  `from_date` and `to_date`, and every `kagi_search` and `kagi_batch_search` was refused.
- An argument set to null counts as left out, as callers that send every argument mean it:
  `format: null` was refused.
- `time` given with dates is refused with how to fix it: leave `time` out to search between the
  dates, or the dates out to search the last period.
- The sign-in page ends as soon as you're done; it could keep the vault waiting 5 more seconds
  when the browser had opened a connection ahead of time.
- When Kagi refuses the session in `KAGI_SESSION_TOKEN`, a search no longer opens the sign-in
  page and waits for you: the variable comes before a kept session, so signing in couldn't fix
  it. The tools and `native/kagi-vault status` say to put a current token in it or remove it.
- A new omp session applies its own project's setting: web_search comes back where Kagi is only
  offered after a session that hid it, and a Kagi failure in one session no longer keeps
  web_search out in front in the next. web_search you turned off yourself stays off.
- In Claude Code, `/clear`, `/resume` and `/branch` start the next conversation over: it no longer
  inherits the last one's Kagi failure or the setting read in another project.

### Security

- The vault is built with Go 1.27.3 and `golang.org/x/net` 0.62.0: its TLS connections to Kagi
  distrust the compromised intermediate certificates (GO-2026-6809), and a crafted result page
  can't slow parsing down quadratically (GO-2026-6860).
