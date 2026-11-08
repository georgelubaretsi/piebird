# piebird-tern-ghostty-style

omp in [Tern](https://docs.stencil.so/tern/), drawn the way omp looks in Ghostty: one box per
tool call, thoughts left open (or foldable, at a keystroke), bash as `$ command`, compact diffs
and replies, and a composer wide enough that a full status line has room for the session cost.
Rendered Markdown files get room for wide tables. On Tern's phone apps, omp keeps its Send
button, which Tern's phone layout otherwise hides along with keyboard shortcut hints.

[![The same omp session in Tern's own look, then in the Ghostty style](../../demos/piebird-tern-ghostty-style/demo.webp)](../../demos/piebird-tern-ghostty-style/demo.mp4)

## Install

    omp plugin marketplace add georgelubaretsi/piebird
    omp plugin install piebird-tern-ghostty-style@piebird

The look is a Tern plugin (`so.stencil.tern/`: style sheets, and the thoughts switch below); omp
brings it along. The next time omp starts in a Tern pane, it installs the look into Tern and says
so in the chat; after `omp plugin upgrade` it updates it the same way; turned off in Tern's
settings, it is left alone. To go back to Tern's own look, uninstall this plugin first
(`omp plugin uninstall piebird-tern-ghostty-style`), then remove the look from Tern
(`tern plugin remove piebird-tern-ghostty-style`); the other way round, omp installs it again.

The agent gets nothing from this plugin.

## Thoughts: open or foldable

Thoughts start left open, as in Ghostty: the text shows under its "Thought for Ns" line, which
has no chevron. To fold them as Tern does, press ⌥⌘T or run **Fold thoughts** from the command
palette (group "Tern Ghostty style"): the chevron comes back, finished thoughts fold to their
head line, and a click on the head or the chevron opens and folds each one. Press ⌥⌘T again, or
run **Keep thoughts open**, to go back. Tern keeps the choice across restarts, for every window;
another open window follows when a pane in it next takes focus.

The chord runs the action `plugin.piebird-tern-ghostty-style.thoughts`: bind that to other keys
in Tern's `keybinds` setting, or set `"alt+cmd+t": "unbind"` there to free ⌥⌘T. The switch lives
in the look's code for desktop windows; Tern's phone apps and its web tab get only the look's
style sheets from the computer they connect to, so phones keep thoughts open and the web tab in a
desktop browser folds them as Tern does. Tern's own Expand thoughts setting works in either mode.
