Web Tools
Web Fetch
The web_fetch tool does a plain HTTP GET and extracts readable content (HTML to markdown or text). It does not execute JavaScript.
For JS-heavy sites or login-protected pages, use the Web Browser instead.
​
Quick start
web_fetch is enabled by default — no configuration needed. The agent can call it immediately:
await web_fetch({ url: "https://example.com/article" });
​
Tool parameters
Parameter	Type	Description
url	string	URL to fetch (required, http/https only)
extractMode	string	"markdown" (default) or "text"
maxChars	number	Truncate output to this many chars
​
How it works
1
Fetch

Sends an HTTP GET with a Chrome-like User-Agent and Accept-Language header. Blocks private/internal hostnames and re-checks redirects.
2
Extract

Runs Readability (main-content extraction) on the HTML response.
3
Fallback (optional)

If Readability fails and Firecrawl is configured, retries through the Firecrawl API with bot-circumvention mode.
4
Cache

Results are cached for 15 minutes (configurable) to reduce repeated fetches of the same URL.
​
Config
{
  tools: {
    web: {
      fetch: {
        enabled: true, // default: true
        maxChars: 50000, // max output chars
        maxCharsCap: 50000, // hard cap for maxChars param
        maxResponseBytes: 2000000, // max download size before truncation
        timeoutSeconds: 30,
        cacheTtlMinutes: 15,
        maxRedirects: 3,
        readability: true, // use Readability extraction
        userAgent: "Mozilla/5.0 ...", // override User-Agent
      },
    },
  },
}
​
Firecrawl fallback
If Readability extraction fails, web_fetch can fall back to Firecrawl for bot-circumvention and better extraction:
{
  tools: {
    web: {
      fetch: {
        firecrawl: {
          enabled: true,
          apiKey: "fc-...", // optional if FIRECRAWL_API_KEY is set
          baseUrl: "https://api.firecrawl.dev",
          onlyMainContent: true,
          maxAgeMs: 86400000, // cache duration (1 day)
          timeoutSeconds: 60,
        },
      },
    },
  },
}
tools.web.fetch.firecrawl.apiKey supports SecretRef objects.
If Firecrawl is enabled and its SecretRef is unresolved with no FIRECRAWL_API_KEY env fallback, gateway startup fails fast.
​
Limits and safety
maxChars is clamped to tools.web.fetch.maxCharsCap
Response body is capped at maxResponseBytes before parsing; oversized responses are truncated with a warning
Private/internal hostnames are blocked
Redirects are checked and limited by maxRedirects
web_fetch is best-effort — some sites need the Web Browser
​
Tool profiles
If you use tool profiles or allowlists, add web_fetch or group:web:
{
  tools: {
    allow: ["web_fetch"],
    // or: allow: ["group:web"]  (includes both web_fetch and web_search)
  },
}
​
Related
Web Search — search the web with multiple providers
Web Browser — full browser automation for JS-heavy sites
Firecrawl — Firecrawl search and scrape tools