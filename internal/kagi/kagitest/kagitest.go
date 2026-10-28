// Package kagitest is a fake Kagi for tests: kagi.com and news.kagi.com serving pages and answers
// as Kagi served them (testdata/, captured live and scrubbed), to one session token.
package kagitest

import (
	"embed"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
)

// Token is the one session the fake accepts.
const Token = "fake-session-token-0123456789"

//go:embed testdata
var files embed.FS

// Fixture is a captured page or answer: search.html, news.html, quick.txt, smallweb.xml,
// categories.json or stories.json.
func Fixture(name string) []byte {
	b, err := files.ReadFile("testdata/" + name)
	if err != nil {
		panic(err) // A test names a file that isn't there.
	}
	return b
}

// landing is enough of Kagi's landing page to read as signed out.
const landing = `<html><head><title>Kagi Search - A Premium Search Engine</title></head>
<body>Welcome to Kagi, the paid search engine that gives power back to the user.</body></html>`

// Kagi is a running fake: its address stands for both hosts.
type Kagi struct {
	URL  string
	mu   sync.Mutex
	seen []*http.Request
}

// Seen are the requests the fake got, oldest first.
func (k *Kagi) Seen() []*http.Request {
	k.mu.Lock()
	defer k.mu.Unlock()
	return append([]*http.Request(nil), k.seen...)
}

// Serve starts a fake Kagi for the test.
func Serve(t *testing.T) *Kagi {
	t.Helper()
	k := &Kagi{}
	mux := routes()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		k.mu.Lock()
		k.seen = append(k.seen, r)
		k.mu.Unlock()
		mux.ServeHTTP(w, r)
	}))
	t.Cleanup(srv.Close)
	k.URL = srv.URL
	return k
}

func signedIn(r *http.Request) bool {
	c, err := r.Cookie("kagi_session")
	return err == nil && c.Value == Token
}

func serve(name string) http.HandlerFunc {
	return func(w http.ResponseWriter, _ *http.Request) { _, _ = w.Write(Fixture(name)) }
}

// Bang is where the fake sends a query with a bang, a word starting or ending with !, as Kagi
// sends `osu! replay` to osu!'s own site.
const Bang = "https://bang.example/search"

// page serves a page of the web product to the session, and the sign-in redirect to anyone else.
func page(name string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		switch {
		case !signedIn(r):
			http.Redirect(w, r, "/signin", http.StatusFound)
		case hasBang(r.URL.Query().Get("q")):
			http.Redirect(w, r, Bang+"?q=replay", http.StatusFound)
		default:
			serve(name)(w, r)
		}
	}
}

func hasBang(q string) bool {
	for word := range strings.FieldsSeq(q) {
		if strings.HasPrefix(word, "!") || strings.HasSuffix(word, "!") {
			return true
		}
	}
	return false
}

func routes() *http.ServeMux {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /html/search", page("search.html"))
	mux.HandleFunc("GET /news", page("news.html"))
	mux.HandleFunc("POST /mother/context", page("quick.txt"))
	mux.HandleFunc("GET /{$}", func(w http.ResponseWriter, r *http.Request) {
		if signedIn(r) {
			_, _ = w.Write([]byte("<html><title>Kagi Search</title></html>"))
		} else {
			_, _ = w.Write([]byte(landing))
		}
	})
	mux.HandleFunc("GET /api/v1/smallweb/feed/", serve("smallweb.xml"))
	mux.HandleFunc("GET /api/batches/latest", func(w http.ResponseWriter, _ *http.Request) { _, _ = w.Write([]byte(`{"id":"batch-1"}`)) })
	mux.HandleFunc("GET /api/batches/batch-1/categories", serve("categories.json"))
	mux.HandleFunc("GET /api/batches/batch-1/categories/{ref}/stories", serve("stories.json"))
	mux.HandleFunc("GET /api/batches/batch-1/chaos", func(w http.ResponseWriter, _ *http.Request) {
		_, _ = w.Write([]byte(`{"chaosIndex":42,"chaosDescription":"Calm-ish.","chaosLastUpdated":"2026-10-12T12:00:00Z"}`))
	})
	return mux
}
