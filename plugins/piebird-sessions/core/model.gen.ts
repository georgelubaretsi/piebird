// Generated from model.ftl by `bun run build`; edit model.ftl.
import { Catalog } from "../kit/core/model";

const SOURCE =
	"## The session_read tool: what it does, and what each argument is for.\n\nread = Read an agent's session journal (.jsonl), omp's, Claude Code's or Codex's, by session id, id prefix or path, and line. Read-only: it changes nothing. Without a session (and nothing but find): this project's sessions, or every agent's where the project isn't known, newest first, with each one's id, start, title and first prompt, to find an earlier session to read. With only a line: that entry and what it relates to (the agent text a user's message answered, an ask with its options and what was picked or typed). Without a line or find: the session from its start. before/after page by messages around the line (tool entries only with tools); find searches one session (from line when given); user keeps only the user's words; thinking/tools add the agent's thinking and tool calls; raw returns the exact journal lines (JSONL). The output ends with the next call to make. Use it to read, check or page through a session instead of opening the journal file, whose lines run to tens of thousands of characters.\n\n    For filtering it doesn't do (by role, tool, time, field, or across sessions), run jq or python over the journal file; a call with only a line prints the journal's path first. Journals: omp's under ~/.omp/agent/sessions/<project>/<time>_<id>.jsonl, Claude Code's under ~/.claude/projects/<project>/<id>.jsonl, Codex's under ~/.codex/sessions/<year>/<month>/<day>/rollout-<time>-<id>.jsonl. Each line is one JSON entry; print only the fields you need, never whole lines.\n    .session = Session id, id prefix (13+ characters avoid collisions) or .jsonl path; omit to list this project's sessions\n    .line = 1-based journal line\n    .before = Messages to show before the line\n    .after = Messages to show after the line, or from the start when no line (default 5)\n    .find = Case-insensitive text to search one session for; without a session, the sessions to pick it from\n    .user = Only the user's messages and ask answers\n    .thinking = Include the agent's thinking\n    .tools = Include tool calls and results\n    .raw = Return exact journal lines instead of readable text\n\n# The call to make next, as the output suggests it.\nnext-call = session_read { $arguments }\n# find without a session: the line before the list of sessions to pick from.\nfind-without-session = find searches one session: pick it below, then call session_read with its session and find \"{ $find }\".\n\n## Joining items in one line.\n\njoin-comma = { $a }, { $b }\njoin-dot = { $a } \u00b7 { $b }\njoin-or = { $a } or { $b }\njoin-and = { $a } and { $b }\n\n## An entry: its header, then its parts.\n\nheader = line { $line } \u00b7 { $kind } \u00b7 { $timestamp }\nkind-user = user message\nkind-assistant = assistant\nkind-ask-question = ask question\nkind-ask-answer = ask answer\nkind-tool-result = tool result ({ $tool })\nkind-other-message = other (message, { $role })\nkind-other = other ({ $type })\nkind-unparsable = unparsable\npart-text = { $text }\npart-thinking = {\"[\"}thinking] { $text }\npart-ask = {\"[\"}ask]\n    { $ask }\npart-tool-call = {\"[\"}tool call] { $name } { $arguments }\npart-image = {\"[\"}image]\n# A part longer than a page shows, cut in the middle so its start and end stay.\npart-cut = { $start }\n    \u2026 [{ $count } characters left out] \u2026\n    { $end }\n# A journal line as it is, for raw.\nraw-line = { $raw }\n\n## An ask: each question with its options, then what was picked or typed.\n\nask-question = { $id }: { $question }\nask-option = {\"  \"}- { $label }\nask-option-described = {\"  \"}- { $label }: { $description }\nask-answer = {\"  \"}{ $answers }\nask-picked = picked: { $picked }\nask-typed = typed: \"{ $typed }\"\nask-no-answer = no answer\nask-text = { $text }\n\n## A line with what it relates to (a line alone).\n\ncite-file = { $file }\ncite-answers = answers { $header }\ncite-follows = follows { $header }\ncite-text = { $text }\ncite-cut = \u2026{ $text }\ncite-no-before = answers: no message with text before it\ncite-asked = answers { $header }\ncite-no-ask = answers: no ask call found before it\ncite-answered = answered on line { $line } \u00b7 { $timestamp }\ncite-ended = no answer: the session ends before one\ncite-unanswered = no answer in the next { $lookahead } lines\ncite-around = around: { $call }\n\n## A page of entries.\n\npage-lines = lines { $first }\u2013{ $last } \u00b7 { $count } entries\npage-left-out = page cap of { $cap } characters: left out { $spans }\npage-span-earlier = { $count } earlier entries (lines { $first }\u2013{ $last })\npage-span-later = { $count } later entries (lines { $first }\u2013{ $last })\npage-earlier = earlier: { $call }\npage-earlier-start = earlier: start of session\npage-later = later: { $call }\npage-later-end = later: end of session ({ $length } lines)\npage-empty = no entries to show \u00b7 end of session ({ $length } lines)\n\n## A search.\n\nfind-snippet = { $start ->\n        [cut] \u2026\n       *[whole] {\"\"}\n    }{ $snippet }{ $end ->\n        [cut] \u2026\n       *[whole] {\"\"}\n    }\nfind-count = { $total ->\n        [one] { $total } match\n       *[other] { $total } matches\n    }\nfind-from = { $count } from line { $from }\nfind-shown = { $count }, the first { $shown } shown\nfind-more = more: { $call }\nfind-read = read one: { $call }\n\n## The latest sessions (no session given): this project's, or every agent's where the project isn't known.\n\nlist-header = Sessions in { $folder }, newest first:\nlist-header-older = Sessions in { $folder }, newest first ({ $shown } of { $total }; list the folder for older ones):\nlist-header-all = Sessions of every agent and project, newest first:\nlist-header-all-older = Sessions of every agent and project, newest first ({ $shown } of { $total }):\nlist-item = - { $id } \u00b7 { $started }\nlist-this = this session\nlist-agent = { $agent ->\n    [omp] omp\n    [claude] Claude Code\n   *[codex] Codex\n}\nlist-project = in { $project }\nlist-title = { $title }\nlist-prompt = first prompt: { $prompt }\nlist-read = read one: { $call }\nlist-empty = No sessions in { $folder }.\n\n## The agent's own session, told before a prompt.\n\nself = This session: { $id } ({ $journal })\nself-forked = This session: { $id } ({ $journal }), forked from { $parent }\n\n## What each error means.\n\n# The tool's own code failing (a bug, an unexpected error), and arguments its schema doesn't take.\nerror-crashed = session_read failed: { $cause }\nerror-arguments = the arguments don't fit session_read: { $problem }\nerror-not-found = session { $session } is not in { $roots }\nerror-ambiguous = { $more ->\n        [no] session { $session } matches { $total } sessions; give a longer id:\n       *[yes] session { $session } matches { $total } sessions; give a longer id (the first { $shown } listed):\n    }\nambiguous-file = {\"  \"}{ $file }\nambiguous-file-titled = {\"  \"}{ $file } \u2014 { $title }\nerror-past-end = { $file } has { $count } lines\nerror-before-without-line = before pages back from a line: give the line too (without a line, the session is read from the start)\nerror-find-with-page = find searches from line (or the start); it takes no before or after: leave them out to search, or leave find out to read a page around the line\nerror-list-with-params = without a session, session_read lists this project's sessions and takes nothing but find: give a session to read it\nerror-user-with-details = user shows only the user's words: leave out thinking and tools\nerror-bad-argument = { $name } takes { $kind ->\n        [text] text\n        [count] a whole number of 1 or more\n       *[flag] true or false\n    }\n";

export type Messages = {
	"ambiguous-file": {
		file: string | number;
	};
	"ambiguous-file-titled": {
		file: string | number;
		title: string | number;
	};
	"ask-answer": {
		answers: string | number;
	};
	"ask-no-answer": undefined;
	"ask-option": {
		label: string | number;
	};
	"ask-option-described": {
		description: string | number;
		label: string | number;
	};
	"ask-picked": {
		picked: string | number;
	};
	"ask-question": {
		id: string | number;
		question: string | number;
	};
	"ask-text": {
		text: string | number;
	};
	"ask-typed": {
		typed: string | number;
	};
	"cite-answered": {
		line: string | number;
		timestamp: string | number;
	};
	"cite-answers": {
		header: string | number;
	};
	"cite-around": {
		call: string | number;
	};
	"cite-asked": {
		header: string | number;
	};
	"cite-cut": {
		text: string | number;
	};
	"cite-ended": undefined;
	"cite-file": {
		file: string | number;
	};
	"cite-follows": {
		header: string | number;
	};
	"cite-no-ask": undefined;
	"cite-no-before": undefined;
	"cite-text": {
		text: string | number;
	};
	"cite-unanswered": {
		lookahead: string | number;
	};
	"error-ambiguous": {
		more: string | number;
		session: string | number;
		shown: string | number;
		total: string | number;
	};
	"error-arguments": {
		problem: string | number;
	};
	"error-bad-argument": {
		kind: string | number;
		name: string | number;
	};
	"error-before-without-line": undefined;
	"error-crashed": {
		cause: string | number;
	};
	"error-find-with-page": undefined;
	"error-list-with-params": undefined;
	"error-not-found": {
		roots: string | number;
		session: string | number;
	};
	"error-past-end": {
		count: string | number;
		file: string | number;
	};
	"error-user-with-details": undefined;
	"find-count": {
		total: string | number;
	};
	"find-from": {
		count: string | number;
		from: string | number;
	};
	"find-more": {
		call: string | number;
	};
	"find-read": {
		call: string | number;
	};
	"find-shown": {
		count: string | number;
		shown: string | number;
	};
	"find-snippet": {
		end: string | number;
		snippet: string | number;
		start: string | number;
	};
	"find-without-session": {
		find: string | number;
	};
	header: {
		kind: string | number;
		line: string | number;
		timestamp: string | number;
	};
	"join-and": {
		a: string | number;
		b: string | number;
	};
	"join-comma": {
		a: string | number;
		b: string | number;
	};
	"join-dot": {
		a: string | number;
		b: string | number;
	};
	"join-or": {
		a: string | number;
		b: string | number;
	};
	"kind-ask-answer": undefined;
	"kind-ask-question": undefined;
	"kind-assistant": undefined;
	"kind-other": {
		type: string | number;
	};
	"kind-other-message": {
		role: string | number;
	};
	"kind-tool-result": {
		tool: string | number;
	};
	"kind-unparsable": undefined;
	"kind-user": undefined;
	"list-agent": {
		agent: string | number;
	};
	"list-empty": {
		folder: string | number;
	};
	"list-header": {
		folder: string | number;
	};
	"list-header-all": undefined;
	"list-header-all-older": {
		shown: string | number;
		total: string | number;
	};
	"list-header-older": {
		folder: string | number;
		shown: string | number;
		total: string | number;
	};
	"list-item": {
		id: string | number;
		started: string | number;
	};
	"list-project": {
		project: string | number;
	};
	"list-prompt": {
		prompt: string | number;
	};
	"list-read": {
		call: string | number;
	};
	"list-this": undefined;
	"list-title": {
		title: string | number;
	};
	"next-call": {
		arguments: string | number;
	};
	"page-earlier": {
		call: string | number;
	};
	"page-earlier-start": undefined;
	"page-empty": {
		length: string | number;
	};
	"page-later": {
		call: string | number;
	};
	"page-later-end": {
		length: string | number;
	};
	"page-left-out": {
		cap: string | number;
		spans: string | number;
	};
	"page-lines": {
		count: string | number;
		first: string | number;
		last: string | number;
	};
	"page-span-earlier": {
		count: string | number;
		first: string | number;
		last: string | number;
	};
	"page-span-later": {
		count: string | number;
		first: string | number;
		last: string | number;
	};
	"part-ask": {
		ask: string | number;
	};
	"part-cut": {
		count: string | number;
		end: string | number;
		start: string | number;
	};
	"part-image": undefined;
	"part-text": {
		text: string | number;
	};
	"part-thinking": {
		text: string | number;
	};
	"part-tool-call": {
		arguments: string | number;
		name: string | number;
	};
	"raw-line": {
		raw: string | number;
	};
	read: undefined;
	"read.after": undefined;
	"read.before": undefined;
	"read.find": undefined;
	"read.line": undefined;
	"read.raw": undefined;
	"read.session": undefined;
	"read.thinking": undefined;
	"read.tools": undefined;
	"read.user": undefined;
	self: {
		id: string | number;
		journal: string | number;
	};
	"self-forked": {
		id: string | number;
		journal: string | number;
		parent: string | number;
	};
};

export const model = new Catalog<Messages>(SOURCE);
