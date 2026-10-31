---
description: Every project keeps a CHANGELOG.md; every change users would notice adds an entry in the same change
---
# Changelog

Required in every project, whatever its own policy says:

- One per independently versioned thing, at its root; also where nothing is ever released.
- A change users would notice (behavior, interfaces, configuration, install steps, security)
  adds an entry in the same change, written for them; any other change says so, by default
  with a `Changelog: none` line in the commit message.
- A tool writes it (release-please, semantic-release, changesets, towncrier, …): the entry is
  the tool's input (a commit message written for users, or a fragment); never edit its output.
- None yet: create it at the first notable change; don't backfill.
- Run the project's changelog check, if it has one.

Format: the project's own where it has one, otherwise Keep a Changelog 2.0.0:

- Entries under `## [Unreleased]`, in Added, Changed, Deprecated, Removed, Fixed or Security;
  a breaking one starts with **Breaking:**.
- Releasing renames `[Unreleased]` to `[<version>] - YYYY-MM-DD` in the version-bump commit
  and opens a new one. Never released: the first change of a month first closes it into the
  previous month's `[YYYY.MM] - YYYY-MM-DD`, dated that month's last day.
- Tagged releases on a host with compare views: end with `[Unreleased]: <repo>/compare/<tag>...HEAD`
  and a link per release; tags as the project names them, else `v<version>`.
- New file (its versioning line names the project's scheme, or goes):

```markdown
# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/2.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
```
