// Package kagi is a small Kagi client for agents: web and news search and Quick Answer through
// the signed-in web product (a subscriber's own Session Link, no API credits), and Kagi News and
// the Small Web feed, which are public. It returns data; the program decides how it reads.
//
// The web product has no API: search and news search read the result page's markup, and Quick
// Answer reads the page's own answer stream. When Kagi changes those pages, the parsers here
// change with them (testdata/ holds pages as Kagi served them). The markup classes follow the
// MIT-licensed kagi-cli (github.com/Microck/kagi-cli), which reads the same pages.
package kagi

import (
	"context"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"
)

// Client calls Kagi with one session.
type Client struct {
	HTTP *http.Client
	// Base is the web product's address and NewsBase Kagi News'; tests point them at a fake.
	Base, NewsBase string
	// Token is the session token; empty when none is saved.
	Token string
	// Headers go on every request: the installed Chrome's User-Agent and client hints.
	Headers http.Header
}

// New is a client for the real Kagi.
func New(token string, headers http.Header) *Client {
	return &Client{
		HTTP: &http.Client{
			Timeout: 30 * time.Second,
			// A signed-out session gets a redirect to the sign-in page; see it as such.
			CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse },
		},
		Base:     "https://kagi.com",
		NewsBase: "https://news.kagi.com",
		Token:    token,
		Headers:  headers,
	}
}

// loggedOutMarkers are all on Kagi's landing page, which a signed-out session is shown.
var loggedOutMarkers = []string{
	"<title>Kagi Search - A Premium Search Engine</title>",
	"Welcome to Kagi",
	"paid search engine that gives power back to the user",
}

func loggedOut(body string) bool {
	for _, m := range loggedOutMarkers {
		if !strings.Contains(body, m) {
			return false
		}
	}
	return true
}

// maxBody bounds what is read of one response.
const maxBody = 16 << 20

// request is a request to the web product, method and path with the query q.
func (c *Client) request(ctx context.Context, method, path string, q url.Values) (*http.Request, error) {
	return http.NewRequestWithContext(ctx, method, c.Base+path+"?"+q.Encode(), http.NoBody)
}

// refused says Kagi didn't serve the request here: a redirect, 401 or 403.
func refused(status int) bool {
	return status >= 300 && status < 400 || status == http.StatusUnauthorized || status == http.StatusForbidden
}

// session sends req with the session cookie and returns the body. A redirect, 401 or 403 means
// a signed-out session only when Kagi's home page refuses the session too: a query sends itself
// elsewhere (a bang such as `osu!` sends a search to that site), and the session is fine then.
func (c *Client) session(req *http.Request) (string, error) {
	body, status, location, err := c.send(req)
	if err != nil {
		return "", err
	}
	if refused(status) {
		if err := c.SignedIn(req.Context()); err != nil {
			return "", err
		}
		if location != "" {
			return "", fail("redirected", map[string]any{"to": redirectTarget(req.URL, location)})
		}
	}
	switch {
	case status != http.StatusOK:
		return "", fail("http-status", map[string]any{"status": status, "path": req.URL.Path})
	case loggedOut(body):
		return "", signIn("signed-out")
	}
	return body, nil
}

// send sends req with the session cookie.
func (c *Client) send(req *http.Request) (body string, status int, location string, err error) {
	if c.Token == "" {
		return "", 0, "", signIn("no-session")
	}
	req.AddCookie(&http.Cookie{Name: "kagi_session", Value: c.Token})
	return c.do(req)
}

// redirectTarget is where location, relative to from, points: its host and path, without the
// query, which repeats the search.
func redirectTarget(from *url.URL, location string) string {
	to, err := from.Parse(location)
	if err != nil {
		return location
	}
	return to.Host + to.Path
}

// page loads a page of the web product with the session.
func (c *Client) page(ctx context.Context, path string, q url.Values) (string, error) {
	req, err := c.request(ctx, http.MethodGet, path, q)
	if err != nil {
		return "", err
	}
	req.Header.Set("Accept", "text/html")
	return c.session(req)
}

// public fetches a page or JSON that needs no session.
func (c *Client) public(ctx context.Context, base, path string, q url.Values) (string, error) {
	u := base + path
	if len(q) > 0 {
		u += "?" + q.Encode()
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, u, http.NoBody)
	if err != nil {
		return "", err
	}
	body, status, _, err := c.do(req)
	if err != nil {
		return "", err
	}
	if status != http.StatusOK {
		return "", fail("http-status", map[string]any{"status": status, "path": path})
	}
	return body, nil
}

func (c *Client) do(req *http.Request) (body string, status int, location string, err error) {
	for k, v := range c.Headers {
		req.Header[k] = v
	}
	resp, err := c.HTTP.Do(req)
	if err != nil {
		return "", 0, "", failWith("cannot-reach", err, nil)
	}
	defer func() { _ = resp.Body.Close() }()
	b, err := io.ReadAll(io.LimitReader(resp.Body, maxBody))
	if err != nil {
		return "", 0, "", failReading("answer", err)
	}
	return string(b), resp.StatusCode, resp.Header.Get("Location"), nil
}

// SignedIn reports whether Kagi accepts the client's session, by loading its home page: a
// redirect, 401 or 403 there, or the landing page, means it doesn't.
func (c *Client) SignedIn(ctx context.Context) error {
	req, err := c.request(ctx, http.MethodGet, "/", url.Values{})
	if err != nil {
		return err
	}
	req.Header.Set("Accept", "text/html")
	body, status, _, err := c.send(req)
	switch {
	case err != nil:
		return err
	case refused(status), status == http.StatusOK && loggedOut(body):
		return signIn("signed-out")
	case status != http.StatusOK:
		return fail("http-status", map[string]any{"status": status, "path": "/"})
	}
	return nil
}
