// Generated from model.ftl by `bun run build`; edit model.ftl.
import { Catalog } from "../kit/core/model";

const SOURCE =
	"## The Kagi tools: what each does, and what each argument is for.\n\nformat-argument = markdown (the default) to read; json for the data as fields, to filter it or pass it on\nlang-argument = Language of Kagi News, e.g. en, de, ja (default en)\n\nsearch = Search the web with Kagi. Returns markdown: each result's title linked to its page, its date and a snippet.\n    .query = What to search for\n    .time = Only results from this last period\n    .from_date = Only results from this date on, YYYY-MM-DD\n    .to_date = Only results up to this date, YYYY-MM-DD\n    .limit = Results to return (default 10)\n    .format = { format-argument }\nbatch-search = Run several Kagi web searches at once (up to 10 queries), with the same filters; one result list per query.\n    .queries = The searches\n    .time = Only results from this last period\n    .from_date = Only results from this date on, YYYY-MM-DD\n    .to_date = Only results up to this date, YYYY-MM-DD\n    .limit = Results to return per search (default 10)\n    .format = { format-argument }\nquick = Ask Kagi's Quick Answer: a short answer written from live search results, with its sources as footnotes.\n    .query = The question\n    .format = { format-argument }\nstatus = Whether a Kagi session is kept on this computer, where, and whether Kagi accepts it.\n    .format = { format-argument }\nnews-search = Search the News tab of kagi.com: articles with their source and age.\n    .query = What to search for\n    .freshness = Only articles from this last period\n    .limit = Results to return (default 10)\n    .format = { format-argument }\nnews = Today's Kagi News stories in a category, each summarized with its sources.\n    .category = A category's name or id, such as World, Technology, Science, Business or Sports; kagi_news_categories lists all of today's (default world)\n    .lang = { lang-argument }\n    .limit = Stories to return (default 10)\n    .hide = Stories to leave out: preset ids from kagi_news_filter_presets, or keywords\n    .format = { format-argument }\nnews-categories = List today's Kagi News categories: the id kagi_news takes, the name and the story count.\n    .lang = { lang-argument }\n    .format = { format-argument }\nnews-chaos = Kagi News' chaos index today: how unsettled world news looks, 0 to 100, with Kagi's reasons.\n    .lang = { lang-argument }\n    .format = { format-argument }\nnews-filter-presets = List Kagi News' content-filter presets, which kagi_news can hide, with their keywords.\n    .lang = Language of the keywords, e.g. en, de, ja (default en)\n    .format = { format-argument }\nsmallweb = The newest posts of Kagi's Small Web feed: personal sites and blogs.\n    .limit = Posts to return (default 10)\n    .format = { format-argument }\nraw-read = Raw mode, for what the other tools don't cover: GET any page or JSON endpoint of kagi.com (signed in) or news.kagi.com and get the response as it came: status, type, body. For anything but a plain GET, use kagi_raw_write.\n    .request = A path on kagi.com (`/html/search?q=x&l=lens`) or an https URL on kagi.com or news.kagi.com\n    .format = { format-argument }\nraw-write = Raw mode for requests that may change the person's Kagi account (settings, lenses, Assistant threads) or that need another method than GET; the response comes as it came: status, type, body. Header lines look like `Content-Type: application/json`; without a Content-Type, a JSON body is sent as JSON and any other as a form. Plain reads go through kagi_raw_read.\n    .request = The whole request in HTTP's form: `POST /path` (or a full URL on kagi.com or news.kagi.com), optional header lines, a blank line, then the body\n    .format = { format-argument }\n\n## What the model is told about searching, by the \"search\" setting (core/settings.json).\n\ninstructions = { $search ->\n        [only] Search the web only with the Kagi tools (kagi_search, kagi_batch_search and the other kagi_ tools): never with a built-in web search, another search engine or another search tool. When they fail, use the kagi skill's command-line fallback; when that fails too, say so. Fetch the pages a search finds with your usual fetch or read tool.\n        [first] Search the web with the Kagi tools (kagi_search, kagi_batch_search and the other kagi_ tools) first. A built-in web search or another search tool is for when the Kagi tools and the kagi skill's command-line fallback fail, or when the person asks for one. Fetch the pages a search finds with your usual fetch or read tool.\n       *[offered] The Kagi tools (kagi_search, kagi_batch_search and the other kagi_ tools) search the web through Kagi, with the person's own Kagi account.\n    }\n# Codex's answer to a web.run search it refuses.\nrefused-web-run = { $search ->\n        [only] Searching with web.run is off: this person searches the web only with Kagi.\n       *[first] Searching with web.run is off while the Kagi tools work.\n    } Search with the `kagi_search` tool, or `kagi_batch_search` for several queries at once; the kagi skill has the rest. web.run still opens pages and runs its other commands.\n# Claude Code's answer to a WebSearch call it refuses.\nrefused-web-search = { $search ->\n        [only] WebSearch is off: this person searches the web only with Kagi.\n       *[first] WebSearch is off while the Kagi tools work.\n    } Search with `kagi_search` (`mcp__piebird-kagi-search__kagi_search`), or `kagi_batch_search` for several queries at once; the kagi skill has the rest.\n\n## Answers: a list of results, stories or posts; one item per line, details after \" \u00b7 \".\n\nresult = { $n }. [{ $title }]({ $url })\nwith-detail = { $line } \u00b7 { $detail }\nresult-snippet = {\"   \"}{ $snippet }\nresults-none = No results.\nbatch-query = ## { $query }\nanswer = { $answer }\nanswer-references = { $references }\nstory-heading = ### { $heading }\nstory-summary = { $summary }\nstory-sources = Sources: { $sources }\nstory-source = [{ $name }]({ $url })\nstories-none = No stories.\ncategory = - `{ $id }`: { $name } ({ $stories ->\n        [one] { $stories } story\n       *[other] { $stories } stories\n    })\nchaos = Chaos index: { $index }/100 (updated { $updated })\nchaos-description = { $description }\npreset = - `{ $id }` ({ $label }): { $keywords }\nposts-none = No posts.\njoin-comma = { $a }, { $b }\n# The data as JSON, for format json.\njson = { $json }\n\n## Raw mode: Kagi's response as it came.\n\nresponse-head = HTTP { $status } { $type }\nresponse-location = { $head } \u2192 { $location }\nresponse-truncated = { $head } (the first { $mb } MB of the body)\nresponse-body = { $body }\nresponse-saved = The body is { $kb } KB, too long to send whole, so it is saved in { $path } ({ $type }). Read it a part at a time with your file tools (grep, jq for JSON, a range of lines).\nresponse-preview = It starts:\nfenced =\n    { $fence }\n    { $text }\n    { $fence }\n\n## The session: whether one is kept, where, and whether Kagi accepts it.\n\nstatus-signed-in = Signed in to Kagi: the session works ({ $from }).\nstatus-refused = A Kagi session is kept ({ $from }), but Kagi doesn't accept it: { $problem }\nstatus-none = Not signed in to Kagi. The first search opens a sign-in page in the browser.\nsource = { $kind ->\n        [env] the { $env } environment variable\n        [keychain] the macOS Keychain\n        [credential-manager] Windows Credential Manager\n        [secret-service] the keyring (the Secret Service)\n       *[file] { $path }, readable only by the person\n    }\n\n## What each error means.\n\n# A tool's own code failing (a bug, an unexpected error), and arguments its schema doesn't take.\nerror-crashed = the plugin failed: { $cause }\nerror-arguments = the arguments don't fit this tool: { $problem }\nerror-bad-input = the arguments don't fit this tool: { $cause }\nerror-failed = the plugin's vault failed: { $cause }\nerror-vault = the plugin's vault (its program that keeps the Kagi session) didn't answer: { $detail }\nerror-one-of = { $name } is one of { $values }, not \"{ $got }\"\nerror-empty-query = the query is empty\nerror-limit = limit is 1 to 50\nerror-time-and-dates = give time or from_date/to_date, not both: leave time out to search between the dates, or the dates out to search the last period\nerror-date = dates are YYYY-MM-DD, not \"{ $got }\"\nerror-dates-order = from_date { $from } is after to_date { $to }\nerror-queries = give 1 to 10 queries, not { $got }\n# A batch's error names the query it came from.\nerror-in-query = \"{ $query }\": { $error }\nerror-sign-in-needed = Kagi needs a sign-in ({ $why ->\n        [signed-out] Kagi no longer accepts the kept session\n       *[no-session] no Kagi session is kept on this computer\n    }). { $opened ->\n        [yes] A page opened in the person's browser: { $page }. Ask them to follow it (copy their Kagi Session Link and paste it there), then call this tool again.\n        [no] The browser didn't open ({ $problem }). Ask the person to open { $page } on this computer and follow it, then call this tool again.\n       *[no-page] The sign-in page couldn't start ({ $problem }).\n    } Without a browser on this computer: `\"{ $vault }\" sign-in --link` in a terminal, then paste the link from https://kagi.com/settings/user_details when it asks.\nerror-env-session-refused = Kagi doesn't accept the session in { $env }, which is set where this agent runs and comes before a kept session, so signing in won't help. Ask the person to put the token from their current Kagi Session Link (https://kagi.com/settings/user_details) in { $env }, or to remove { $env } and sign in.\nerror-secret-store = cannot { $doing ->\n        [save] save\n        [forget] remove\n       *[read] read\n    } the Kagi session in { $store ->\n        [keychain] the macOS Keychain\n        [credential-manager] Windows Credential Manager\n        [secret-service] the keyring (the Secret Service)\n        [file] the plugin's secrets file\n       *[other] the secret store\n    }: { $cause }\nerror-signed-out = Kagi no longer accepts the kept session (it signed it out)\nerror-http-status = Kagi answered HTTP { $status } for { $path }\nerror-cannot-reach = cannot reach Kagi: { $cause }\nerror-reading = reading { $what ->\n        [results] Kagi's result page\n        [news] Kagi News\n        [news-page] Kagi's news page\n        [smallweb] the Small Web feed\n       *[answer] Kagi's answer\n    }: { $cause }\nerror-no-quick-answer = Kagi gave no quick answer for this query\nerror-no-batch = Kagi News has no current batch\nerror-no-category = Kagi News has no category \"{ $want }\" today; kagi_news_categories lists the { $count } it has\nerror-raw-read-method = kagi_raw_read only reads (GET); send { $method } through kagi_raw_write\nerror-raw-read-target = give one path on kagi.com (/html/search?q=x) or one https URL on kagi.com or news.kagi.com\nerror-raw-read-sign-out = kagi_raw_read leaves the sign-out page alone: it ends the person's Kagi session\nerror-raw-write-start = start with the method and the target, e.g. \"POST /path\" or \"DELETE https://kagi.com/...\"\nerror-raw-write-header = \"{ $line }\" isn't a header line (Name: value); a blank line goes before the body\nerror-raw-write-cookie = leave out Cookie and Host: the session and the host are set for Kagi\nerror-target = the target is a path on kagi.com (/html/search?q=...) or an https URL on kagi.com or news.kagi.com\nerror-host = only kagi.com and news.kagi.com, not { $host }: the session goes to Kagi alone\nerror-cannot-keep = cannot keep the long body in a file: { $cause }\n";

export type Messages = {
	answer: {
		answer: string | number;
	};
	"answer-references": {
		references: string | number;
	};
	"batch-query": {
		query: string | number;
	};
	"batch-search": undefined;
	"batch-search.format": undefined;
	"batch-search.from_date": undefined;
	"batch-search.limit": undefined;
	"batch-search.queries": undefined;
	"batch-search.time": undefined;
	"batch-search.to_date": undefined;
	category: {
		id: string | number;
		name: string | number;
		stories: string | number;
	};
	chaos: {
		index: string | number;
		updated: string | number;
	};
	"chaos-description": {
		description: string | number;
	};
	"error-arguments": {
		problem: string | number;
	};
	"error-bad-input": {
		cause: string | number;
	};
	"error-cannot-keep": {
		cause: string | number;
	};
	"error-cannot-reach": {
		cause: string | number;
	};
	"error-crashed": {
		cause: string | number;
	};
	"error-date": {
		got: string | number;
	};
	"error-dates-order": {
		from: string | number;
		to: string | number;
	};
	"error-empty-query": undefined;
	"error-env-session-refused": {
		env: string | number;
	};
	"error-failed": {
		cause: string | number;
	};
	"error-host": {
		host: string | number;
	};
	"error-http-status": {
		path: string | number;
		status: string | number;
	};
	"error-in-query": {
		error: string | number;
		query: string | number;
	};
	"error-limit": undefined;
	"error-no-batch": undefined;
	"error-no-category": {
		count: string | number;
		want: string | number;
	};
	"error-no-quick-answer": undefined;
	"error-one-of": {
		got: string | number;
		name: string | number;
		values: string | number;
	};
	"error-queries": {
		got: string | number;
	};
	"error-raw-read-method": {
		method: string | number;
	};
	"error-raw-read-sign-out": undefined;
	"error-raw-read-target": undefined;
	"error-raw-write-cookie": undefined;
	"error-raw-write-header": {
		line: string | number;
	};
	"error-raw-write-start": undefined;
	"error-reading": {
		cause: string | number;
		what: string | number;
	};
	"error-secret-store": {
		cause: string | number;
		doing: string | number;
		store: string | number;
	};
	"error-sign-in-needed": {
		opened: string | number;
		page: string | number;
		problem: string | number;
		vault: string | number;
		why: string | number;
	};
	"error-signed-out": undefined;
	"error-target": undefined;
	"error-time-and-dates": undefined;
	"error-vault": {
		detail: string | number;
	};
	fenced: {
		fence: string | number;
		text: string | number;
	};
	"format-argument": undefined;
	instructions: {
		search: string | number;
	};
	"join-comma": {
		a: string | number;
		b: string | number;
	};
	json: {
		json: string | number;
	};
	"lang-argument": undefined;
	news: undefined;
	"news-categories": undefined;
	"news-categories.format": undefined;
	"news-categories.lang": undefined;
	"news-chaos": undefined;
	"news-chaos.format": undefined;
	"news-chaos.lang": undefined;
	"news-filter-presets": undefined;
	"news-filter-presets.format": undefined;
	"news-filter-presets.lang": undefined;
	"news-search": undefined;
	"news-search.format": undefined;
	"news-search.freshness": undefined;
	"news-search.limit": undefined;
	"news-search.query": undefined;
	"news.category": undefined;
	"news.format": undefined;
	"news.hide": undefined;
	"news.lang": undefined;
	"news.limit": undefined;
	"posts-none": undefined;
	preset: {
		id: string | number;
		keywords: string | number;
		label: string | number;
	};
	quick: undefined;
	"quick.format": undefined;
	"quick.query": undefined;
	"raw-read": undefined;
	"raw-read.format": undefined;
	"raw-read.request": undefined;
	"raw-write": undefined;
	"raw-write.format": undefined;
	"raw-write.request": undefined;
	"refused-web-run": {
		search: string | number;
	};
	"refused-web-search": {
		search: string | number;
	};
	"response-body": {
		body: string | number;
	};
	"response-head": {
		status: string | number;
		type: string | number;
	};
	"response-location": {
		head: string | number;
		location: string | number;
	};
	"response-preview": undefined;
	"response-saved": {
		kb: string | number;
		path: string | number;
		type: string | number;
	};
	"response-truncated": {
		head: string | number;
		mb: string | number;
	};
	result: {
		n: string | number;
		title: string | number;
		url: string | number;
	};
	"result-snippet": {
		snippet: string | number;
	};
	"results-none": undefined;
	search: undefined;
	"search.format": undefined;
	"search.from_date": undefined;
	"search.limit": undefined;
	"search.query": undefined;
	"search.time": undefined;
	"search.to_date": undefined;
	smallweb: undefined;
	"smallweb.format": undefined;
	"smallweb.limit": undefined;
	source: {
		env: string | number;
		kind: string | number;
		path: string | number;
	};
	status: undefined;
	"status-none": undefined;
	"status-refused": {
		from: string | number;
		problem: string | number;
	};
	"status-signed-in": {
		from: string | number;
	};
	"status.format": undefined;
	"stories-none": undefined;
	"story-heading": {
		heading: string | number;
	};
	"story-source": {
		name: string | number;
		url: string | number;
	};
	"story-sources": {
		sources: string | number;
	};
	"story-summary": {
		summary: string | number;
	};
	"with-detail": {
		detail: string | number;
		line: string | number;
	};
};

export const model = new Catalog<Messages>(SOURCE);
