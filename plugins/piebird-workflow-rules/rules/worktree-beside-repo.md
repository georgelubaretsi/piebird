---
description: Make worktrees beside their repo as ../<repo>-<slug>, never inside a checkout
condition: 'worktree(?:\s|\\\n|\\\\\\n)+add(?:(?:\s|\\\n|\\\\\\n)+(?:-[bB](?:\s|\\\n|\\\\\\n)+(?:\\?["''][^"''\\]*\\?["'']|[^\s"''\\]+)|--[\w-]*|-[^bB\s-]\w*))*(?:\s|\\\n|\\\\\\n)+(?:\\?["''])?(?!\.\./)(?!-)[^\s"''\\]+(?:\s|\\?["'']|\\)'
scope: tool:bash, tool:eval
interruptMode: tool-only
---
Worktrees go beside their repo, never inside a checkout, where everything that copies or walks
the checkout reaches them: `git -C <repo> worktree add -b <type>/<slug> ../<repo>-<slug>
origin/<branch>`.
