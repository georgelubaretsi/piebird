package kagi

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"piebird.dev/plugins/internal/ops"
)

var ctx = context.Background()

func TestSearchReadsKagisResultPage(t *testing.T) {
	c, _ := fakeKagi(t)
	results, err := c.Search(ctx, Query{Text: "golang http client timeout", Limit: 3})
	if err != nil || len(results) != 3 {
		t.Fatalf("%d results, err %v", len(results), err)
	}
	want := Result{
		Title: "The complete guide to Go net/http timeouts",
		URL:   "https://blog.cloudflare.com/the-complete-guide-to-golang-net-http-timeouts/",
		Date:  "2016-06-29",
	}
	got := results[0]
	if got.Title != want.Title || got.URL != want.URL || got.Date != want.Date || !strings.HasPrefix(got.Snippet, "Client-side timeouts") {
		t.Errorf("first result: %+v", got)
	}
}

func TestSearchSendsTheQueryAsTheBrowserWould(t *testing.T) {
	c, k := fakeKagi(t)
	if _, err := c.Search(ctx, Query{Text: "golang http client timeout", Time: "year"}); err != nil {
		t.Fatal(err)
	}
	req := k.Seen()[0]
	if q := req.URL.Query(); q.Get("q") != "golang http client timeout" || q.Get("dr") != "year" {
		t.Errorf("query sent: %v", q)
	}
	if req.Header.Get("User-Agent") != "test-agent" || req.Header.Get("Sec-Ch-Ua-Platform") != `"macOS"` {
		t.Errorf("headers sent: %v", req.Header)
	}
}

func TestSearchListsEachPageOnce(t *testing.T) {
	c, _ := fakeKagi(t)
	all, err := c.Search(ctx, Query{Text: "x", Limit: 50})
	if err != nil || len(all) < 10 {
		t.Fatalf("%d results, err %v", len(all), err)
	}
	urls := map[string]bool{}
	for _, r := range all {
		if urls[r.URL] || !strings.HasPrefix(r.URL, "http") || r.Title == "" {
			t.Errorf("bad or repeated result %+v", r)
		}
		urls[r.URL] = true
	}
}

func TestSearchRefusesBadFilters(t *testing.T) {
	c, k := fakeKagi(t)
	for _, q := range []Query{
		{Text: " "},
		{Text: "x", Time: "decade"},
		{Text: "x", Time: "week", From: "2026-01-01"},
		{Text: "x", From: "2026-13-01"},
		{Text: "x", From: "2026-02-01", To: "2026-01-01"},
		{Text: "x", Limit: 51},
	} {
		if _, err := c.Search(ctx, q); err == nil || errors.Is(err, ErrSignIn) {
			t.Errorf("%+v: err %v", q, err)
		}
	}
	if len(k.Seen()) != 0 {
		t.Errorf("a refused query reached Kagi")
	}
}

func TestSignedOutSessionsNeedASignIn(t *testing.T) {
	c, _ := fakeKagi(t)
	for name, token := range map[string]string{"no session": "", "rejected session": "stale-token-0123456789"} {
		c.Token = token
		_, err := c.Search(ctx, Query{Text: "x"})
		if !errors.Is(err, ErrSignIn) {
			t.Errorf("%s: search error %v", name, err)
		}
		if err := c.SignedIn(ctx); !errors.Is(err, ErrSignIn) {
			t.Errorf("%s: SignedIn %v", name, err)
		}
		if _, err := c.Quick(ctx, "x"); !errors.Is(err, ErrSignIn) {
			t.Errorf("%s: quick error %v", name, err)
		}
	}
	c.Token = goodToken
	if err := c.SignedIn(ctx); err != nil {
		t.Errorf("good session: %v", err)
	}
}

func TestAnswersElsewhereLeaveTheSessionSignedIn(t *testing.T) {
	// A bang sends a search to another site, and a 403 can refuse one request, while Kagi's home
	// page still takes the session: neither asks for a sign-in.
	c, _ := fakeKagi(t)
	for _, q := range []string{"osu! replay dataset", "!w kagi"} {
		_, err := c.Search(ctx, Query{Text: q})
		if declared := new(ops.Error); errors.Is(err, ErrSignIn) || !errors.As(err, &declared) ||
			declared.ID != "redirected" || declared.Variables["to"] != "bang.example/search" {
			t.Errorf("%q: err %v", q, err)
		}
	}
	forbidden := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/" {
			_, _ = w.Write([]byte("<html><title>Kagi Search</title></html>"))
			return
		}
		w.WriteHeader(http.StatusForbidden)
	}))
	t.Cleanup(forbidden.Close)
	c.Base = forbidden.URL
	_, err := c.Search(ctx, Query{Text: "x"})
	if declared := new(ops.Error); errors.Is(err, ErrSignIn) || !errors.As(err, &declared) ||
		declared.ID != "http-status" || declared.Variables["status"] != http.StatusForbidden {
		t.Errorf("403: err %v", err)
	}
}

func TestQuickAnswerKeepsItsMarkdownAndSources(t *testing.T) {
	c, _ := fakeKagi(t)
	answer, err := c.Quick(ctx, "boiling point of water at sea level")
	if err != nil {
		t.Fatal(err)
	}
	mustContain(t, answer.Answer, "**100 °C (212 °F)**", "[^3]")
	mustContain(t, answer.References, "[^1]: [Boiling point](https://en.wikipedia.org/wiki/Boiling_point)")
}

func TestQuickFallsBackToTheAnswerSoFar(t *testing.T) {
	stream := "hi:{}\x00\ntokens.json:{\"text\":\"<p>Partial <b>answer</b></p>\"}\x00\n"
	if got, err := parseQuick(stream); err != nil || got.Answer != "Partial answer" {
		t.Errorf("tokens only: %+v %v", got, err)
	}
	if _, err := parseQuick("hi:{}\x00\n"); err == nil {
		t.Error("an empty stream gave an answer")
	}
}

func TestNewsSearchReadsTheNewsTab(t *testing.T) {
	c, k := fakeKagi(t)
	results, err := c.NewsSearch(ctx, "openai", "week", 2)
	if err != nil {
		t.Fatal(err)
	}
	if len(results) != 2 || results[0].Source != "engadget.com" || results[0].Age != "11 hours ago" ||
		!strings.Contains(results[0].Title, "OpenAI") || !strings.HasPrefix(results[0].URL, "https://") {
		t.Errorf("results: %+v", results)
	}
	if f := k.Seen()[0].URL.Query().Get("freshness"); f != "week" {
		t.Errorf("freshness sent: %q", f)
	}
	if _, err := c.NewsSearch(ctx, "openai", "year", 2); err == nil {
		t.Error("freshness year was accepted")
	}
}

func TestNewsPicksTheCategoryAndHidesStories(t *testing.T) {
	c, k := fakeKagi(t)
	stories, err := c.News(ctx, NewsQuery{Category: "Madeira Island", Lang: "en", Limit: 10})
	if err != nil || len(stories) != 2 {
		t.Fatalf("stories %d, err %v", len(stories), err)
	}
	if seen := k.Seen(); seen[len(seen)-1].URL.Path != "/api/batches/batch-1/categories/bd96baf8-ca7f-4bad-9d2f-032caf1d5b87/stories" {
		t.Errorf("stories path %s", seen[len(seen)-1].URL.Path)
	}
	hidden, _ := c.News(ctx, NewsQuery{Category: "madeira_island", Lang: "en", Limit: 10, Hide: NewFilter([]string{"Cruises"}, "en")})
	if len(hidden) != 1 || hidden[0].Category != "Figure Skating" {
		t.Errorf("hiding by keyword: %+v", hidden)
	}
	_, err = c.News(ctx, NewsQuery{Category: "nowhere", Lang: "en", Limit: 10})
	if declared := new(ops.Error); !errors.As(err, &declared) || declared.ID != "no-category" || declared.Variables["count"] != 3 {
		t.Errorf("unknown category: %v", err)
	}
}

func TestChaosAndSmallWeb(t *testing.T) {
	c, _ := fakeKagi(t)
	ch, err := c.Chaos(ctx, "en")
	if err != nil || ch.Index != 42 || ch.Description != "Calm-ish." {
		t.Errorf("chaos %+v %v", ch, err)
	}
	posts, err := c.SmallWeb(ctx, 1)
	if err != nil || len(posts) != 1 || posts[0].Published != "2026-10-14" || !strings.HasPrefix(posts[0].URL, "https://") {
		t.Errorf("small web %+v %v", posts, err)
	}
}
