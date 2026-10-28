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

- Your messages are a dark bar again, not a white one you can't read, and tool boxes take omp's
  success, pending and error tints again, with omp 18.13.3 or Tern 0.9.7, which no longer pass
  omp's colours to Tern. The look brings omp dark-arctic's palette itself (`palette.css`).
  Version 0.1.5, so omp replaces 0.1.4 in Tern.
- Bold around inline code stays bold, in a table and out: a reply's bold `after-kagi`, such as
  the default marked among choices, showed as plain code, since Tern gives code a weight of its
  own. Plain bold in table cells was bold already. Version 0.1.4, so omp replaces 0.1.3 in Tern.
- On Tern's phone apps, Send shows an up arrow instead of a hatched box. Its key cap is the
  character ⏎, which the apps' built-in font lacks on Android; the arrow is drawn in CSS, in the
  button's own colour. Version 0.1.2, so omp replaces 0.1.1 in Tern.
- With a full status line, such as omp's `nerd` preset, the composer bar has room for the session
  cost again. Reader capped the composer at 736px, and Tern cut the cost, the thinking level and
  the folder from the bar for lack of room. The composer now grows to 1200px in a wide pane: with
  every item showing, that bar needs about 1,080px (0.1.2 made it 880px, as wide as the
  transcript, which a long session's cost still outgrew). Version 0.1.3. Phones are unchanged.
