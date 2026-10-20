# Changelog

All notable changes to this plugin are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/2.0.0/),
and this plugin adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Tern plugin `piebird-tern-ghostty-style` (folder `so.stencil.tern/`), a look: style sheets that draw
  omp's chat in Tern's Reader chat style the way omp looks in Ghostty: one box per tool call
  with its heading (title, intent) inside, eval cells included; thoughts left open under their
  "Thought for Ns" line; bash as `$ command`; diffs with one line-number column; your messages
  as full-width bars, denser replies and text in omp dark-arctic's colours. Outside omp,
  rendered Markdown in file panes gets a column up to 1200px instead of Tern's 832px, so wide
  tables and diagrams aren't cut while the pane stays empty around them. It needs Tern 0.7.1 or
  later.
- omp installs the look: when omp starts as the main agent in a local Tern pane, it installs
  the Tern plugin if Tern lacks it, replaces a copy of another version (after a plugin upgrade),
  and says so in the chat. A linked copy and one turned off in Tern's settings are left alone.
- Supported hosts: omp, and Tern through omp.
- README, with a demo video: the same omp session in Tern's own look, then in this one.
- On Tern's phone apps (iPhone, Android, a browser tab on a phone), omp's Send button and the
  esc button that closes a subagent's transcript show again. Tern's phone layout hides keyboard
  shortcut hints, and these two buttons are drawn as nothing but one: a prompt went only with the
  keyboard's Enter key, and the transcript had no button to close it. Version 0.1.1, so omp
  replaces a look an earlier version installed in Tern (after `omp plugin upgrade`).

### Fixed

- On Tern's phone apps, Send shows an up arrow instead of a hatched box. Its key cap is the
  character ⏎, which the apps' built-in font lacks on Android; the arrow is drawn in CSS, in the
  button's own colour. Version 0.1.2, so omp replaces 0.1.1 in Tern.
- With a full status line, such as omp's `nerd` preset, the composer bar has room for the session
  cost again. Reader capped the composer at 736px under an 880px transcript, and Tern cut the
  cost, the thinking level and the folder from the bar for lack of room. The composer is now as
  wide as the transcript, as omp's status line spans the terminal in Ghostty. Narrow panes and
  phones are unchanged.
