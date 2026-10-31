# piebird-workflow-rules

Rules and a skill on how to work, for any project: weigh problems in proportion, think before
building, fix a correction as a class of mistakes, use the project's own tools, keep the
changelog, name commits and branches, and ask only for real decisions.

[![omp, Claude Code and Codex fix the same reported bug under the same rules](../../demos/piebird-workflow-rules/demo.webp)](../../demos/piebird-workflow-rules/demo.mp4)

## Install

    omp plugin marketplace add georgelubaretsi/piebird
    omp plugin install piebird-workflow-rules@piebird

Claude Code: `claude plugin marketplace add georgelubaretsi/piebird`, then
`claude plugin install piebird-workflow-rules@piebird`. Codex: `codex plugin marketplace add
georgelubaretsi/piebird`, then `codex plugin add piebird-workflow-rules@piebird`. ChatGPT and
Claude on a Mac or a Windows PC: the piebird installer ([Install](../../README.md#install)).

## What it adds

| Rule | What it holds | How omp loads it |
| --- | --- | --- |
| `piebird-workflow-rules` | think before building, proportion, recurring corrections | in full, every agent |
| `piebird-workflow-rules-main` | asking for decisions | in full, the main agent |
| `piebird-workflow-rules-reviewer` | what a reviewer reports | in full, the `reviewer` agent |
| `project-tooling`, `changelog`, `commits-and-branches` | the project's own tools; changelogs; commit and branch names | listed; the agent reads one when it applies |

Claude Code doesn't load rules from a plugin, so the plugin's mod puts them in a block of the
conversation's context: the always-applied ones for the main agent in full, the others by name
and file; the reviewer's rule stays out. Codex gets the skill.

The skill `failure-classes` lists ten general failure classes, each with its members and how to
test them.

[What the model sees](../../docs/model/piebird-workflow-rules.md): every rule and the skill, word
for word, and the block Claude Code gets.

## Codex code review

Codex code review doesn't load plugins. To give it the same bar for findings as the `reviewer`
agent, paste the text of `rules/piebird-workflow-rules-reviewer.md` (below its frontmatter) into
ChatGPT Settings > Code Review, and paste it again when this plugin's changelog says that rule
changed. OpenAI documents the setting for reviews started in the ChatGPT app; check that your
GitHub reviews follow it too.
