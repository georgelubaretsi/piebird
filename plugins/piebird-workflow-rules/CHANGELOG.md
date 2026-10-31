# Changelog

All notable changes to this plugin are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/2.0.0/),
and this plugin adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- In Claude Code, a mod (`com.anthropic.claudecode/`) puts the rules in a block of the
  conversation's context, at its start and after compaction or `/clear`: the always-applied ones
  for the main agent in full, the others by name and file, for the agent to read when one fits.
  The reviewer's rule stays out.
- For Codex, the skill.
- Supported hosts: omp, Claude Code, Codex.
- [What the model sees](../../docs/model/piebird-workflow-rules.md): every rule and the skill as
  the agents get them.
- Rule `piebird-workflow-rules` (in full, every agent), in three sections: think before building
  (before a non-trivial change, find what already defines or solves it, state what must be true,
  and decide how it fails); proportion (weigh each possible problem by how likely it is in real
  use, how much it would hurt and what handling it costs; leave what's unlikely and minor, and
  call work done when only such issues remain); recurring corrections (weigh a correction first,
  then fix the class of the mistake rather than the one example, and stop to redesign when
  corrections repeat).
- Rule `piebird-workflow-rules-main` (in full, main agent only), asking for decisions: don't ask
  what you can find out; explain and discuss in plain text and use the ask tool only for the
  final pick, each option saying what you get and what you give up; keep discussing in plain text
  when the user cancels the ask tool and writes instead; take a clear safe default and say so,
  continue agreed work without asking.
- Rule `piebird-workflow-rules-reviewer` (in full, the `reviewer` agent): report a finding only
  when acting on it is worth more than it costs. The README shows how to give Codex code review
  the same text.
- Rule `project-tooling`: use the project's own dev shell, scripts, lockfiles and CI steps; write
  AGENTS.md as a README for agents (fixed sections, short bullets, detail in `docs/`, 2–5 code
  review rules each with a safe path, the threat model in `docs/threat-model.md`).
- Rule `changelog`: every project keeps a CHANGELOG.md, and every change users would notice adds
  an entry in the same change. Where a tool writes the changelog (release-please,
  semantic-release, changesets, towncrier), the entry is that tool's input and its output is
  never edited. The format is the project's own, otherwise Keep a Changelog; a project that
  never releases closes its Unreleased section into a dated monthly section at the first change
  of a new month.
- Rule `commits-and-branches`: commit messages in Conventional Commits 1.0.0 and branch names
  starting with `feat/`, `fix/`, `hotfix/` or `chore/`, unless the project names them its own
  way. Names only: when and how to branch, merge and release stays the project's.
- Skill `failure-classes`: ten general failure classes, each with its members and how to test them.
- README, with a demo video: omp fixes a reported bug and the other place with the same flaw,
  with tests.

### Changed

- The always-applied rules are named for whom they are: `proportion`, `think-before-building`
  and `recurring-corrections` are one rule, `piebird-workflow-rules` (same text, its sections
  pointing at each other); `ask-for-decisions` is `piebird-workflow-rules-main` and
  `proportion-review` `piebird-workflow-rules-reviewer`. A rule turned off by its old name in
  omp's `disabledRules` needs the new one.
- Renamed from `workflow` to `piebird-workflow-rules`, one name for the folder, `plugin.json`,
  `package.json` and the catalog: install it as `piebird-workflow-rules@piebird`.
