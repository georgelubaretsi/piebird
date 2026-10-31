---
description: Name commits per Conventional Commits 1.0.0 and branches feat/, fix/, hotfix/ or chore/<slug>, unless the project names them its own way
---
# Commits and branches

Names only; when and how to branch, merge and release is the project's. Its own naming
(AGENTS.md, CONTRIBUTING, a commit check, recent `git log`) wins over this.

- Commits: Conventional Commits 1.0.0; footers are git trailers, `Changelog: none` among them
  (rule: changelog).
- Branches: `<prefix>/<slug>`, the slug in lowercase kebab-case: `feat/` a new feature, `fix/` a
  bug fix, `hotfix/` an urgent fix to something released or live, `chore/` anything else.
