# piebird-tern-ghostty-style

omp in [Tern](https://docs.stencil.so/tern/), drawn the way omp looks in Ghostty: one box per
tool call, thoughts left open, bash as `$ command`, compact diffs and replies. Rendered Markdown
files get room for wide tables. On Tern's phone apps, omp keeps its Send button, which Tern's
phone layout otherwise hides along with keyboard shortcut hints.

[![The same omp session in Tern's own look, then in the Ghostty style](../../demos/piebird-tern-ghostty-style/demo.webp)](../../demos/piebird-tern-ghostty-style/demo.mp4)

## Install

    omp plugin marketplace add georgelubaretsi/piebird
    omp plugin install piebird-tern-ghostty-style@piebird

The look is a Tern plugin (`so.stencil.tern/`, style sheets only); omp brings it along. The next
time omp starts in a Tern pane, it installs the look into Tern and says so in the chat; after
`omp plugin upgrade` it updates it the same way; turned off in Tern's settings, it is left alone.
To go back to Tern's own look, uninstall this plugin first
(`omp plugin uninstall piebird-tern-ghostty-style`), then remove the look from Tern
(`tern plugin remove piebird-tern-ghostty-style`); the other way round, omp installs it again.

The agent gets nothing from this plugin.
