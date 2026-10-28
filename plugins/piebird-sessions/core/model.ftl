## The session_read tool: what it does, and what each argument is for.

read = Read an agent's session journal (.jsonl), omp's, Claude Code's or Codex's, by session id, id prefix or path, and line. Read-only: it changes nothing. Without a session (and nothing but find): this project's sessions, or every agent's where the project isn't known, newest first, with each one's id, start, title and first prompt, to find an earlier session to read. With only a line: that entry and what it relates to (the agent text a user's message answered, an ask with its options and what was picked or typed). Without a line or find: the session from its start. before/after page by messages around the line (tool entries only with tools); find searches one session (from line when given); user keeps only the user's words; thinking/tools add the agent's thinking and tool calls; raw returns the exact journal lines (JSONL). The output ends with the next call to make. Use it to read, check or page through a session instead of opening the journal file, whose lines run to tens of thousands of characters.

    For filtering it doesn't do (by role, tool, time, field, or across sessions), run jq or python over the journal file; a call with only a line prints the journal's path first. Journals: omp's under ~/.omp/agent/sessions/<project>/<time>_<id>.jsonl, Claude Code's under ~/.claude/projects/<project>/<id>.jsonl, Codex's under ~/.codex/sessions/<year>/<month>/<day>/rollout-<time>-<id>.jsonl. Each line is one JSON entry; print only the fields you need, never whole lines.
    .session = Session id, id prefix (13+ characters avoid collisions) or .jsonl path; omit to list this project's sessions
    .line = 1-based journal line
    .before = Messages to show before the line
    .after = Messages to show after the line, or from the start when no line (default 5)
    .find = Case-insensitive text to search one session for; without a session, the sessions to pick it from
    .user = Only the user's messages and ask answers
    .thinking = Include the agent's thinking
    .tools = Include tool calls and results
    .raw = Return exact journal lines instead of readable text

# The call to make next, as the output suggests it.
next-call = session_read { $arguments }
# find without a session: the line before the list of sessions to pick from.
find-without-session = find searches one session: pick it below, then call session_read with its session and find "{ $find }".

## Joining items in one line.

join-comma = { $a }, { $b }
join-dot = { $a } · { $b }
join-or = { $a } or { $b }
join-and = { $a } and { $b }

## An entry: its header, then its parts.

header = line { $line } · { $kind } · { $timestamp }
kind-user = user message
kind-assistant = assistant
kind-ask-question = ask question
kind-ask-answer = ask answer
kind-tool-result = tool result ({ $tool })
kind-other-message = other (message, { $role })
kind-other = other ({ $type })
kind-unparsable = unparsable
part-text = { $text }
part-thinking = {"["}thinking] { $text }
part-ask = {"["}ask]
    { $ask }
part-tool-call = {"["}tool call] { $name } { $arguments }
part-image = {"["}image]
# A part longer than a page shows, cut in the middle so its start and end stay.
part-cut = { $start }
    … [{ $count } characters left out] …
    { $end }
# A journal line as it is, for raw.
raw-line = { $raw }

## An ask: each question with its options, then what was picked or typed.

ask-question = { $id }: { $question }
ask-option = {"  "}- { $label }
ask-option-described = {"  "}- { $label }: { $description }
ask-answer = {"  "}{ $answers }
ask-picked = picked: { $picked }
ask-typed = typed: "{ $typed }"
ask-no-answer = no answer
ask-text = { $text }

## A line with what it relates to (a line alone).

cite-file = { $file }
cite-answers = answers { $header }
cite-follows = follows { $header }
cite-text = { $text }
cite-cut = …{ $text }
cite-no-before = answers: no message with text before it
cite-asked = answers { $header }
cite-no-ask = answers: no ask call found before it
cite-answered = answered on line { $line } · { $timestamp }
cite-ended = no answer: the session ends before one
cite-unanswered = no answer in the next { $lookahead } lines
cite-around = around: { $call }

## A page of entries.

page-lines = lines { $first }–{ $last } · { $count } entries
page-left-out = page cap of { $cap } characters: left out { $spans }
page-span-earlier = { $count } earlier entries (lines { $first }–{ $last })
page-span-later = { $count } later entries (lines { $first }–{ $last })
page-earlier = earlier: { $call }
page-earlier-start = earlier: start of session
page-later = later: { $call }
page-later-end = later: end of session ({ $length } lines)
page-empty = no entries to show · end of session ({ $length } lines)

## A search.

find-snippet = { $start ->
        [cut] …
       *[whole] {""}
    }{ $snippet }{ $end ->
        [cut] …
       *[whole] {""}
    }
find-count = { $total ->
        [one] { $total } match
       *[other] { $total } matches
    }
find-from = { $count } from line { $from }
find-shown = { $count }, the first { $shown } shown
find-more = more: { $call }
find-read = read one: { $call }

## The latest sessions (no session given): this project's, or every agent's where the project isn't known.

list-header = Sessions in { $folder }, newest first:
list-header-older = Sessions in { $folder }, newest first ({ $shown } of { $total }; list the folder for older ones):
list-header-all = Sessions of every agent and project, newest first:
list-header-all-older = Sessions of every agent and project, newest first ({ $shown } of { $total }):
list-item = - { $id } · { $started }
list-this = this session
list-agent = { $agent ->
    [omp] omp
    [claude] Claude Code
   *[codex] Codex
}
list-project = in { $project }
list-title = { $title }
list-prompt = first prompt: { $prompt }
list-read = read one: { $call }
list-empty = No sessions in { $folder }.

## The agent's own session, told before a prompt.

self = This session: { $id } ({ $journal })
self-forked = This session: { $id } ({ $journal }), forked from { $parent }

## What each error means.

# The tool's own code failing (a bug, an unexpected error), and arguments its schema doesn't take.
error-crashed = session_read failed: { $cause }
error-arguments = the arguments don't fit session_read: { $problem }
error-not-found = session { $session } is not in { $roots }
error-ambiguous = { $more ->
        [no] session { $session } matches { $total } sessions; give a longer id:
       *[yes] session { $session } matches { $total } sessions; give a longer id (the first { $shown } listed):
    }
ambiguous-file = {"  "}{ $file }
ambiguous-file-titled = {"  "}{ $file } — { $title }
error-past-end = { $file } has { $count } lines
error-before-without-line = before pages back from a line: give the line too (without a line, the session is read from the start)
error-find-with-page = find searches from line (or the start); it takes no before or after: leave them out to search, or leave find out to read a page around the line
error-list-with-params = without a session, session_read lists this project's sessions and takes nothing but find: give a session to read it
error-user-with-details = user shows only the user's words: leave out thinking and tools
error-bad-argument = { $name } takes { $kind ->
        [text] text
        [count] a whole number of 1 or more
       *[flag] true or false
    }
