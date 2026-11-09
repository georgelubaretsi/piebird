---
description: Worktrees go beside their repo as <repo>-<slug>, never inside a checkout or copied from one; read before making a worktree, cloning a repo or adding upstream sources, data or program state
agents: main
---
# Workspace layout

```
<workspace>/          umbrella git repo (every workspace has one)
  .gitignore          allowlist: /*, then !/<file> for each tracked file
  workspace.repos     repos to clone (vcs2l)
  <repo>/             a repo, ignored
  <repo>-<slug>/      its worktree for branch <type>/<slug>, ignored
  reference/<name>    link to an upstream source, ignored
```

- A repo's checkout holds its tracked files and its build output, nothing else.
- Worktree: `git -C <repo> worktree add -b <type>/<slug> ../<repo>-<slug> origin/<branch>`;
  remove it once merged. A repo too big to check out whole: add `--no-checkout`, then in the
  worktree `git sparse-checkout set --cone --sparse-index <dirs>` and `git checkout`.
- Upstream source: a flake input with `flake = false`, linked at `reference/<name>` by the dev
  shell. A source that is only web pages: a scheduled job in a repo of yours fetches and commits
  it; pin that repo.
- Data: a data repo whose git tracks one `.dvc` file per folder: `dvc add <folder>`, commit the
  `.dvc` file, `dvc push`. Every data repo and worktree shares one cache:
  `dvc cache dir --global ~/.local/share/dvc/cache`.
- Program state: `~/.local/state/<project>/`.
