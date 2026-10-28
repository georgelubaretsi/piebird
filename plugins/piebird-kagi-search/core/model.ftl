## The Kagi tools: what each does, and what each argument is for.

format-argument = markdown (the default) to read; json for the data as fields, to filter it or pass it on
lang-argument = Language of Kagi News, e.g. en, de, ja (default en)

search = Search the web with Kagi. Returns markdown: each result's title linked to its page, its date and a snippet.
    .query = What to search for
    .time = Only results from this last period
    .from_date = Only results from this date on, YYYY-MM-DD
    .to_date = Only results up to this date, YYYY-MM-DD
    .limit = Results to return (default 10)
    .format = { format-argument }
batch-search = Run several Kagi web searches at once (up to 10 queries), with the same filters; one result list per query.
    .queries = The searches
    .time = Only results from this last period
    .from_date = Only results from this date on, YYYY-MM-DD
    .to_date = Only results up to this date, YYYY-MM-DD
    .limit = Results to return per search (default 10)
    .format = { format-argument }
quick = Ask Kagi's Quick Answer: a short answer written from live search results, with its sources as footnotes.
    .query = The question
    .format = { format-argument }
status = Whether a Kagi session is kept on this computer, where, and whether Kagi accepts it.
    .format = { format-argument }
news-search = Search the News tab of kagi.com: articles with their source and age.
    .query = What to search for
    .freshness = Only articles from this last period
    .limit = Results to return (default 10)
    .format = { format-argument }
news = Today's Kagi News stories in a category, each summarized with its sources.
    .category = A category's name or id, such as World, Technology, Science, Business or Sports; kagi_news_categories lists all of today's (default world)
    .lang = { lang-argument }
    .limit = Stories to return (default 10)
    .hide = Stories to leave out: preset ids from kagi_news_filter_presets, or keywords
    .format = { format-argument }
news-categories = List today's Kagi News categories: the id kagi_news takes, the name and the story count.
    .lang = { lang-argument }
    .format = { format-argument }
news-chaos = Kagi News' chaos index today: how unsettled world news looks, 0 to 100, with Kagi's reasons.
    .lang = { lang-argument }
    .format = { format-argument }
news-filter-presets = List Kagi News' content-filter presets, which kagi_news can hide, with their keywords.
    .lang = Language of the keywords, e.g. en, de, ja (default en)
    .format = { format-argument }
smallweb = The newest posts of Kagi's Small Web feed: personal sites and blogs.
    .limit = Posts to return (default 10)
    .format = { format-argument }
raw-read = Raw mode, for what the other tools don't cover: GET any page or JSON endpoint of kagi.com (signed in) or news.kagi.com and get the response as it came: status, type, body. For anything but a plain GET, use kagi_raw_write.
    .request = A path on kagi.com (`/html/search?q=x&l=lens`) or an https URL on kagi.com or news.kagi.com
    .format = { format-argument }
raw-write = Raw mode for requests that may change the person's Kagi account (settings, lenses, Assistant threads) or that need another method than GET; the response comes as it came: status, type, body. Header lines look like `Content-Type: application/json`; without a Content-Type, a JSON body is sent as JSON and any other as a form. Plain reads go through kagi_raw_read.
    .request = The whole request in HTTP's form: `POST /path` (or a full URL on kagi.com or news.kagi.com), optional header lines, a blank line, then the body
    .format = { format-argument }

## What the model is told about searching, by the "search" setting (core/settings.json).

instructions = { $search ->
        [only] Search the web only with the Kagi tools (kagi_search, kagi_batch_search and the other kagi_ tools): never with a built-in web search, another search engine or another search tool. When they fail, use the kagi skill's command-line fallback; when that fails too, say so. Fetch the pages a search finds with your usual fetch or read tool.
        [first] Search the web with the Kagi tools (kagi_search, kagi_batch_search and the other kagi_ tools) first. A built-in web search or another search tool is for when the Kagi tools and the kagi skill's command-line fallback fail, or when the person asks for one. Fetch the pages a search finds with your usual fetch or read tool.
       *[offered] The Kagi tools (kagi_search, kagi_batch_search and the other kagi_ tools) search the web through Kagi, with the person's own Kagi account.
    }
# Codex's answer to a web.run search it refuses.
refused-web-run = { $search ->
        [only] Searching with web.run is off: this person searches the web only with Kagi.
       *[first] Searching with web.run is off while the Kagi tools work.
    } Search with the `kagi_search` tool, or `kagi_batch_search` for several queries at once; the kagi skill has the rest. web.run still opens pages and runs its other commands.
# Claude Code's answer to a WebSearch call it refuses.
refused-web-search = { $search ->
        [only] WebSearch is off: this person searches the web only with Kagi.
       *[first] WebSearch is off while the Kagi tools work.
    } Search with `kagi_search` (`mcp__piebird-kagi-search__kagi_search`), or `kagi_batch_search` for several queries at once; the kagi skill has the rest.

## Answers: a list of results, stories or posts; one item per line, details after " · ".

result = { $n }. [{ $title }]({ $url })
with-detail = { $line } · { $detail }
result-snippet = {"   "}{ $snippet }
results-none = No results.
batch-query = ## { $query }
answer = { $answer }
answer-references = { $references }
story-heading = ### { $heading }
story-summary = { $summary }
story-sources = Sources: { $sources }
story-source = [{ $name }]({ $url })
stories-none = No stories.
category = - `{ $id }`: { $name } ({ $stories ->
        [one] { $stories } story
       *[other] { $stories } stories
    })
chaos = Chaos index: { $index }/100 (updated { $updated })
chaos-description = { $description }
preset = - `{ $id }` ({ $label }): { $keywords }
posts-none = No posts.
join-comma = { $a }, { $b }
# The data as JSON, for format json.
json = { $json }

## Raw mode: Kagi's response as it came.

response-head = HTTP { $status } { $type }
response-location = { $head } → { $location }
response-truncated = { $head } (the first { $mb } MB of the body)
response-body = { $body }
response-saved = The body is { $kb } KB, too long to send whole, so it is saved in { $path } ({ $type }). Read it a part at a time with your file tools (grep, jq for JSON, a range of lines).
response-preview = It starts:
fenced =
    { $fence }
    { $text }
    { $fence }

## The session: whether one is kept, where, and whether Kagi accepts it.

status-signed-in = Signed in to Kagi: the session works ({ $from }).
status-refused = A Kagi session is kept ({ $from }), but Kagi doesn't accept it: { $problem }
status-none = Not signed in to Kagi. The first search opens a sign-in page in the browser.
source = { $kind ->
        [env] the { $env } environment variable
        [keychain] the macOS Keychain
        [credential-manager] Windows Credential Manager
        [secret-service] the keyring (the Secret Service)
       *[file] { $path }, readable only by the person
    }

## What each error means.

# A tool's own code failing (a bug, an unexpected error), and arguments its schema doesn't take.
error-crashed = the plugin failed: { $cause }
error-arguments = the arguments don't fit this tool: { $problem }
error-bad-input = the arguments don't fit this tool: { $cause }
error-failed = the plugin's vault failed: { $cause }
error-vault = the plugin's vault (its program that keeps the Kagi session) didn't answer: { $detail }
error-one-of = { $name } is one of { $values }, not "{ $got }"
error-empty-query = the query is empty
error-limit = limit is 1 to 50
error-time-and-dates = give time or from_date/to_date, not both: leave time out to search between the dates, or the dates out to search the last period
error-date = dates are YYYY-MM-DD, not "{ $got }"
error-dates-order = from_date { $from } is after to_date { $to }
error-queries = give 1 to 10 queries, not { $got }
# A batch's error names the query it came from.
error-in-query = "{ $query }": { $error }
error-sign-in-needed = Kagi needs a sign-in ({ $why ->
        [signed-out] Kagi no longer accepts the kept session
       *[no-session] no Kagi session is kept on this computer
    }). { $opened ->
        [yes] A page opened in the person's browser: { $page }. Ask them to follow it (copy their Kagi Session Link and paste it there), then call this tool again.
        [no] The browser didn't open ({ $problem }). Ask the person to open { $page } on this computer and follow it, then call this tool again.
       *[no-page] The sign-in page couldn't start ({ $problem }).
    } Without a browser on this computer: `"{ $vault }" sign-in --link` in a terminal, then paste the link from https://kagi.com/settings/user_details when it asks.
error-env-session-refused = Kagi doesn't accept the session in { $env }, which is set where this agent runs and comes before a kept session, so signing in won't help. Ask the person to put the token from their current Kagi Session Link (https://kagi.com/settings/user_details) in { $env }, or to remove { $env } and sign in.
error-secret-store = cannot { $doing ->
        [save] save
        [forget] remove
       *[read] read
    } the Kagi session in { $store ->
        [keychain] the macOS Keychain
        [credential-manager] Windows Credential Manager
        [secret-service] the keyring (the Secret Service)
        [file] the plugin's secrets file
       *[other] the secret store
    }: { $cause }
error-signed-out = Kagi no longer accepts the kept session (it signed it out)
error-http-status = Kagi answered HTTP { $status } for { $path }
error-cannot-reach = cannot reach Kagi: { $cause }
error-reading = reading { $what ->
        [results] Kagi's result page
        [news] Kagi News
        [news-page] Kagi's news page
        [smallweb] the Small Web feed
       *[answer] Kagi's answer
    }: { $cause }
error-no-quick-answer = Kagi gave no quick answer for this query
error-no-batch = Kagi News has no current batch
error-no-category = Kagi News has no category "{ $want }" today; kagi_news_categories lists the { $count } it has
error-raw-read-method = kagi_raw_read only reads (GET); send { $method } through kagi_raw_write
error-raw-read-target = give one path on kagi.com (/html/search?q=x) or one https URL on kagi.com or news.kagi.com
error-raw-read-sign-out = kagi_raw_read leaves the sign-out page alone: it ends the person's Kagi session
error-raw-write-start = start with the method and the target, e.g. "POST /path" or "DELETE https://kagi.com/..."
error-raw-write-header = "{ $line }" isn't a header line (Name: value); a blank line goes before the body
error-raw-write-cookie = leave out Cookie and Host: the session and the host are set for Kagi
error-target = the target is a path on kagi.com (/html/search?q=...) or an https URL on kagi.com or news.kagi.com
error-host = only kagi.com and news.kagi.com, not { $host }: the session goes to Kagi alone
error-cannot-keep = cannot keep the long body in a file: { $cause }
