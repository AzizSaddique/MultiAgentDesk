# AgentDesk — Phase A.1: Lead Discovery Provider Audit

**Audit Date:** November 5, 2026  
**Auditor:** Antigravity AI Systems Architecture Team  
**Inspection Target:** `backend/providers/search/*`, `backend/providers/mock.py`, `backend/providers/playwright_scraper.py`, `backend/services/lead_discovery.py`

---

## 1. Discovery Provider Inventory & Operational Status

The codebase contains six distinct providers across two subsystems: the **Lead Discovery Search Providers** (`backend/providers/search/`) and the **Interactive Research Providers** (`backend/providers/`).

| Provider ID | Provider Class | File Location | Requires API Key? | Configured Out-of-Box? | Operates Live? | Verification Status |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| `duckduckgo` | `DuckDuckGoLiveSearchProvider` | `search/duckduckgo_search.py` | **No** | **Yes** | **Yes** | **Genuinely Working Live** |
| `directory` | `PublicBusinessDirectoryProvider` | `search/directory_search.py` | **No** | **Yes** | **No** (Static Seed) | **Genuinely Working Offline** |
| `tavily` | `TavilySearchProvider` | `search/tavily_search.py` | **Yes** (`TAVILY_API_KEY`) | No | Yes (When keyed) | **Working Code (Key Required)** |
| `google` | `GoogleSearchProvider` | `search/google_search.py` | **Yes** (`GOOGLE_SEARCH_API_KEY`, `CX`) | No | Yes (When keyed) | **Working Code (Key Required)** |
| `bing` | `BingSearchProvider` | `search/bing_search.py` | **Yes** (`BING_SEARCH_API_KEY`) | No | Yes (When keyed) | **Working Code (Key Required)** |
| `mock` | `MockResearchProvider` | `providers/mock.py` | **No** | **Yes** | **No** (Simulated) | **Genuinely Working Demo** |

---

## 2. In-Depth Analysis of Each Provider

### 2.1 DuckDuckGo Live Search Provider (`duckduckgo`)
- **Implementation:** Executes live HTTP POST requests to `https://html.duckduckgo.com/html/` with payload `{"q": clean_query}` and user agent `AgentDesk/1.0`.
- **Key Requirement:** Zero API keys required.
- **Parsing Logic:** Uses BeautifulSoup to parse `.result`, unpacks DuckDuckGo redirect URLs (`uddg=` query parameter), strips UTM tracking codes, and enforces URL protocol validation (`http://` or `https://`).
- **Rate Pacing:** Enforces an asynchronous lock (`asyncio.Lock()`) with a minimum request interval of 0.5s between consecutive search requests.
- **Vulnerabilities / Risks:**
  1. DuckDuckGo may return HTTP 429 (rate limited) if excessive queries are run from the same residential or cloud IP.
  2. HTML layout changes on `html.duckduckgo.com` can break CSS selector parsing (`div.result`, `a.result__a`, `a.result__snippet`).
- **Operational Assessment:** **Genuinely functional for live unauthenticated web discovery.**

### 2.2 Public Business Directory Search Provider (`directory`)
- **Implementation:** Completely offline, static in-memory Python list (`PUBLIC_DIRECTORY_REGISTRY`) located in `backend/providers/search/directory_search.py`.
- **Dataset Size:** Exactly **23 verified enterprise records**:
  - 5 Lahore/Pakistan Solar companies (Reon Energy, SkyElectric, Premier Energy, Pantera Energy, Zero Carbon).
  - 4 Lahore Software/IoT companies (Systems Limited, Netsol, Tkxel, Contour Software).
  - 14 global technology and commercial firms.
- **Query Mechanism:** Performs regex token matching against `keywords`, `title`, `city`, and `snippet`.
- **Live vs. Seed Distinction:** Results are **100% seeded offline fixtures**. In `lead_discovery.py` line 1135, any lead produced by this provider has `is_live = False` and `discovery_source = "Public Business Directory"`.
- **Operational Assessment:** **Reliable zero-dependency fallback for development and testing.**

### 2.3 Tavily Search API Provider (`tavily`)
- **Implementation:** Official REST integration with `https://api.tavily.com/search`.
- **Credentials:** Reads `TAVILY_API_KEY` or `AGENTDESK_TAVILY_API_KEY` from environment. Rejects dummy values (`placeholder`, `xxx`).
- **Features:** Supports `include_domains`, `exclude_domains`, and sets `search_depth="advanced"`. Includes polite pacing (0.2s minimum interval).
- **Failure Handling:** Catches HTTP errors, checks for quota exhaustion (HTTP 429/432), and sanitizes API keys from error logs.
- **Operational Assessment:** **Production-grade code; requires user to supply an API key.**

### 2.4 Google Custom Search Provider (`google`)
- **Implementation:** Official REST integration with `https://www.googleapis.com/customsearch/v1`.
- **Credentials:** Requires two environment variables: `GOOGLE_SEARCH_API_KEY` and `GOOGLE_SEARCH_ENGINE_ID` (`cx`).
- **Features:** Paginates up to 10 results per query using Google REST parameters `num` and `start`.
- **Failure Handling:** Validates key lengths (>=10 chars for key, >=5 chars for cx). Sanitizes error strings.
- **Operational Assessment:** **Standard Google REST integration; requires GCP API credentials.**

### 2.5 Bing Web Search Provider (`bing`)
- **Implementation:** Official REST integration with Azure Cognitive Services (`https://api.bing.microsoft.com/v7.0/search`).
- **Credentials:** Requires `BING_SEARCH_API_KEY`.
- **Features:** Paginates results using Azure parameters `count` and `offset`.
- **Failure Handling:** Catches `httpx` request exceptions and redacts secrets.
- **Operational Assessment:** **Standard Azure Bing REST integration; requires Azure subscription.**

### 2.6 Mock Research Provider (`mock`)
- **Implementation:** In-memory procedural generator in `backend/providers/mock.py`.
- **Purpose:** Used in Agent 1 "Demo Mode" for rapid UI testing without web access.
- **Output:** Generates simulated lead records clearly marked with `"These records are simulated demo samples... No live web scraping was performed."`
- **Operational Assessment:** **Fully functional demo fixture.**

---

## 3. Fallback Mechanics & Logic Discrepancy

The discovery system has two separate layers of fallback:

### 3.1 Layer 1: Provider Selection Fallback (`factory.py`)
In `get_search_provider(provider_id="auto")`:
1. Checks if `Tavily` is configured. If so, returns Tavily.
2. Checks if `Google` is configured. If so, returns Google.
3. Checks if `Bing` is configured. If so, returns Bing.
4. If none of the commercial APIs are configured:
   - It checks: `if os.environ.get("ENABLE_DDG_AUTO_FALLBACK", "").lower() in ("true", "1", "yes")`: returns `DuckDuckGoLiveSearchProvider()`.
   - **Otherwise, it falls back to `PublicBusinessDirectoryProvider()`!**

> [!WARNING] **Architectural Discrepancy in `factory.py`:**
> In `list_search_providers()` (which populates the UI provider dropdown):
> Line 78-83 states that `auto` routes to "DuckDuckGo Live Search" when no keys are configured:
> `active_auto_source = "DuckDuckGo Live Search"`
> However, in `get_search_provider("auto")`, if `ENABLE_DDG_AUTO_FALLBACK` is NOT set in `.env`, the code actually routes to **`PublicBusinessDirectoryProvider`** (the 23-entry static list)!
> This causes users selecting "Auto-Select" to unknowingly search the static 23-lead fixture instead of live DuckDuckGo unless they explicitly pick DuckDuckGo or set the environment variable.

### 3.2 Layer 2: Empty Result Fallback (`lead_discovery.py`)
In `LeadDiscoveryService._execute_pipeline`:
- If the primary provider (whether Tavily, Google, Bing, or DuckDuckGo) executes and returns **0 results**, lines 717–721 automatically execute a secondary query pass against `PublicBusinessDirectoryProvider`.
- This ensures that a pipeline run rarely returns empty results, but can substitute static fixture leads if a live search query fails.

---

## 4. Discovery Pipeline Reproducibility & Technical Rigor

### 4.1 Retaining Source URLs
- **Yes.** Every discovered lead stores a JSON-serialized array in `discovered_leads.source_urls`.
- For directory leads, the synthetic URL `https://agentdesk.directory/registry` is recorded alongside the company website.
- For live web leads, both the homepage and any inspected contact subpages (`/contact`, `/about`) are recorded.

### 4.2 Deduplication Mechanics
Deduplication is performed in three distinct stages:
1. **Search Candidate Level (`_execute_pipeline`):**
   - Canonical domain normalization: `urlparse(r.url).netloc.lower().replace("www.", "")`.
   - Stripped company name: `re.sub(r'[^a-zA-Z0-9]+', '', r.title.lower())`.
   - If domain or name has already been seen in the *current job*, candidate is dropped and `duplicate_count` is incremented.
2. **Extraction Contact Level (`_execute_pipeline`):**
   - Phone deduplication: Digits stripped (`re.sub(r'\D', '', phone)`); if phone has >=7 digits and was seen in the current job, lead is dropped as duplicate.
3. **Outreach Transfer Level (`transfer_leads_to_outreach`):**
   - Checks `discovered_lead.id`, `disc-{id}`, and `company_name` against existing records in `outreach_drafts` and `DRAFT_REGISTRY`. If a draft already exists and is not rejected, draft creation is skipped.

> [!IMPORTANT] **Deduplication Gap:**
> Search candidate deduplication is **scoped only to the active job**. If an operator runs Job A (discovering 20 leads) and subsequently runs Job B with similar keywords, Job B does not query `discovered_leads` to skip domains already discovered in Job A. Cross-job deduplication only occurs during the *Transfer to Outreach* phase.

### 4.3 Rate Limiting & Robots.txt Compliance
- **Robots.txt:** Implemented via `is_allowed_by_robots(url, user_agent="AgentDesk-Bot/1.0", timeout=3.0)`. Fetches `robots.txt` using `urllib.request` and parses rules via `urllib.robotparser.RobotFileParser`. If disallowed, the candidate is immediately skipped with outcome `"skipped"`.
- **Crawl Pacing:** A per-domain timestamp map (`self._domain_last_visited`) enforces a mandatory 0.4s delay between visits to the same host.
- **Concurrency Limit:** Crawling is throttled using `asyncio.Semaphore(3)`, preventing excessive concurrent connections.
- **Depth Limiter:** Hardcapped at `max_crawl_depth=1` and `max_pages_per_domain=2` to prevent infinite crawl spidering.

---

## 5. Summary Findings for Discovery

1. **DuckDuckGo is the only live search provider that works without credentials.**
2. **The Public Business Directory contains exactly 23 static records and is not live.**
3. **Provider failure recording is fully implemented** (`discovery_jobs.error_message`, `current_stage`, and status = `failed`).
4. **Source URLs and verified fields are reliably preserved** in the database.
5. **The `ENABLE_DDG_AUTO_FALLBACK` bug in `factory.py` must be resolved** so "Auto-Select" genuinely defaults to DuckDuckGo when commercial keys are absent.
6. **Cross-job deduplication must be added** to prevent re-crawling identical domains across different discovery jobs.

