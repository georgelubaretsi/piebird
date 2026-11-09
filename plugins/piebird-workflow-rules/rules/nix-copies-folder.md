---
description: Never give Nix a folder as a `path:` reference or `getFlake` of a plain path; it copies the whole folder into the store
condition:
  - '\bnix\b[^\n]*\bpath:'
  - 'getFlake(?:\s|\\[nt])*\(?(?:\s|\\[nt])*(?:\((?:\s|\\[nt])*toString|\\?"?[./~])'
  - 'url\s*=\s*\\?"path:'
scope: tool:bash, tool:eval, tool:edit(*.nix), tool:write(*.nix)
interruptMode: tool-only
---
`path:` references and `getFlake` of a plain path make Nix copy the whole folder into the store,
git-ignored repos, `.git` and build output included. Use `.#<attr>` from inside the repo, or
`git+file:///<repo>?rev=<commit>`.
