# AgentDesk — Phase A.1: Website & Technology Auditor Readiness

**Audit Date:** November 5, 2026  
**Auditor:** Antigravity AI Systems Architecture Team  
**Evaluation Target:** Readiness of Playwright subsystem (`backend/providers/playwright_scraper.py`), HTTP client architecture, and security boundaries to support an automated **Website & Technology Auditor Engine**.

---

## 1. Readiness Audit for Audit Dimensions

To transform AgentDesk into an Agency + SaaS OS, the engine must audit prospective client websites to diagnose technical vulnerabilities, automation gaps, and digital modernization opportunities that form the basis of agency proposals.

| Audit Dimension | Existing Code Support | Readiness Assessment | Required Technical Additions |
| :--- | :---: | :---: | :--- |
| **Website Availability & Uptime** | Basic `httpx.get()` / Playwright navigation checks HTTP status code (200 vs 4xx/5xx). | **Low** | Needs SSL certificate validation (expiry date, issuer, cipher), DNS resolution timing, and TLS handshake latency tracking. |
| **Mobile Responsiveness** | Playwright can resize viewport, but existing code uses a fixed desktop viewport (`1280x720`). | **Low** | Needs automated dual-viewport testing (Desktop `1440x900` vs. Mobile `375x667`), horizontal scroll detection, touch target sizing check (<48px). |
| **SEO Basics** | Extracts `<title>` and `<meta name="description">`. | **Medium-Low** | Needs H1/H2 header hierarchy analysis, canonical URL presence, robots.txt directives, sitemap.xml validation, OpenGraph / Twitter Card completeness, image alt-tag audit. |
| **Performance Indicators** | Measures overall navigation timeout (defaults to 15s/30s). | **Low** | Needs programmatic measurement of Google Core Web Vitals: Largest Contentful Paint (LCP), Time to First Byte (TTFB), Cumulative Layout Shift (CLS), and total page payload size. |
| **Technology Stack Detection** | Checks if page uses WordPress / Wix in email cleaner domains. | **Very Low** | Needs comprehensive signature-based tech detector (Wappalyzer / BuiltWith alternative) scanning HTTP response headers, meta generators, script sources, and cookie names for CMS, server, framework, analytics, and CRM pixels. |
| **Contact & Conversion Opportunities** | Regex extracts `mailto:` and `tel:` links; detects `/contact` and `/about` subpages. | **Medium** | Needs heuristic detection of interactive contact forms, embedded Google Maps, direct WhatsApp floating widgets, click-to-call buttons, and lead magnet forms. |
| **Customer Portal Availability** | None. | **Unbuilt (0%)** | Needs login/portal link detector (`/login`, `/portal`, `/client-area`, `/dashboard`) to evaluate whether the business provides digital self-service. |
| **Booking / Quotation Functionality** | None. | **Unbuilt (0%)** | Needs pattern detection for third-party booking widgets (Calendly, Acuity, HubSpot Meetings) and interactive cost calculators/quotation forms. |
| **Visible Automation Gaps** | None. | **Unbuilt (0%)** | Needs heuristics identifying manual PDF order forms, non-clickable email/phone text, missing net-metering solar calculators, or unautomated enquiry workflows. |

---

## 2. Security & Crawling Risk Analysis

### 2.1 Critical Vulnerability: Server-Side Request Forgery (SSRF)
The current URL validation logic in `backend/providers/playwright_scraper.py` (lines 30–63) contains critical security flaws:

```python
# Current implementation in playwright_scraper.py:
def validate_target_url(raw_url: str):
    ...
    hostname = parsed.hostname
    if (
        hostname in ("localhost", "127.0.0.1", "0.0.0.0")
        or hostname.startswith("192.168.")
        or hostname.startswith("10.")
        or hostname.startswith("172.16.")
    ):
        return False, cleaned, "Internal / private network URLs are restricted."
```

#### SSRF Bypass Vectors in Current Code:
1. **DNS Rebinding:** `validate_target_url` only inspects the string value of `parsed.hostname`. An attacker-controlled domain (e.g. `rebind.attacker.com`) can return a public IP on initial check and resolve to `127.0.0.1` upon Playwright/httpx connection.
2. **Incomplete Private IP Coverage (RFC 1918):**
   - The code checks `hostname.startswith("172.16.")`.
   - The actual RFC 1918 private range for Class B is `172.16.0.0/12` (`172.16.0.0` to `172.31.255.255`).
   - Addresses such as `172.17.x.x`, `172.20.x.x`, and `172.31.x.x` **completely bypass** this check!
3. **Cloud Metadata Services:**
   - Link-local IP `169.254.169.254` (AWS, GCP, Azure instance metadata) is **not blocked**.
4. **IPv6 Loopback & Link-Local:**
   - IPv6 addresses like `[::1]`, `[fe80::1]` (link-local), and `[fc00::1]` (unique local) are **not blocked**.
5. **Alternative IP Encodings:**
   - Octal (`0177.0.0.1`), hexadecimal (`0x7f.0x0.0x0.0x1`), or decimal integer notation (`2130706433`) bypass `.startswith("127.0.0.1")`.

> [!CAUTION] **SSRF Remediation Required Before Production:**
> The URL validator must perform **DNS pre-resolution** via `socket.getaddrinfo()`, resolve all IP addresses for the target host, and validate each IP against `ipaddress.ip_network.is_private`, `is_loopback`, `is_link_local`, `is_reserved`, and `is_multicast`.

### 2.2 Unsafe Redirects
- When following HTTP redirects via `httpx(follow_redirects=True)` or Playwright page navigation, a target public URL can redirect to an internal private URL (`http://company.com` -> `http://169.254.169.254/latest/meta-data`).
- `lead_discovery.py` lines 964–969 re-checks the final redirected URL, but `playwright_scraper.py` does not hook into Playwright's `route.continue()` to intercept redirects at the network layer.

### 2.3 Resource Exhaustion & Denial of Service (DoS)
- Headless Chromium instances spawned by Playwright consume significant RAM (150–300 MB per tab).
- Crawling complex single-page apps (SPAs) with infinite scrolls or heavy WebGL can exhaust host memory.
- `page.goto()` timeout must be strictly capped (e.g., 10.0s), with image, font, and media loading disabled (`route.abort()` on image/media requests) to keep audits lightweight.

---

## 3. Proposed Website & Technology Auditor Architecture

```
+-----------------------------------------------------------------------------------+
|                        WEBSITE & TECHNOLOGY AUDITOR ENGINE                        |
+-----------------------------------------------------------------------------------+
                                         |
    +------------------------------------+------------------------------------+
    |                                    |                                    |
    v                                    v                                    v
+-----------------------+    +-----------------------+    +-----------------------+
| 1. Network & Security |    | 2. Tech Stack Scanner |    | 3. Conversion Audit   |
| - Pre-DNS SSRF Guard  |    | - Signature Matching  |    | - Form/Booking Detect |
| - SSL/TLS Certificate |    | - CMS: WordPress/etc. |    | - Portal/Login Check  |
| - HTTP Security Hdrs  |    | - Server & CDN        |    | - Calculator Audit    |
| - TTFB & Response Code|    | - Analytics & Pixels  |    | - WhatsApp Widget     |
+-----------------------+    +-----------------------+    +-----------------------+
    |                                    |                                    |
    +------------------------------------+------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                         4. Performance & Core Web Vitals                          |
|  - Playwright Headless Audit (Emulated Mobile + Desktop)                          |
|  - TTFB, LCP, CLS, Page Weight, Script Execution Time                             |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                         5. Agency Opportunity Generator                           |
|  Synthesizes an Executive Audit Card:                                             |
|  - Overall Digital Health: (A - F Grade)                                          |
|  - Modernization Gap: Outdated Stack, Missing Quotation Tool, Slow Mobile LCP     |
|  - Pitched Solution: Custom Web Portal + Automated Net-Metering Workflow          |
+-----------------------------------------------------------------------------------+
```

### Proposed Output Schema: `WebsiteAuditReport`
```json
{
  "domain": "example-solar.com",
  "audit_timestamp": "2026-11-05T15:00:00Z",
  "overall_grade": "D+",
  "security": {
    "https_enforced": true,
    "ssl_valid": true,
    "ssl_days_remaining": 42,
    "security_headers_missing": ["Strict-Transport-Security", "Content-Security-Policy"]
  },
  "performance": {
    "ttfb_ms": 1420,
    "lcp_seconds": 5.4,
    "cls_score": 0.28,
    "total_payload_kb": 8420,
    "mobile_responsive": false
  },
  "tech_stack": {
    "cms": "WordPress 5.4 (Outdated)",
    "server": "Apache 2.4",
    "frameworks": ["jQuery 1.12.4"],
    "analytics": ["Google Analytics 4"],
    "cdn": null
  },
  "conversion_assets": {
    "has_contact_form": true,
    "has_booking_widget": false,
    "has_customer_portal": false,
    "has_quotation_calculator": false,
    "whatsapp_click_to_chat": true
  },
  "agency_opportunities": [
    "Website takes 5.4s to load on mobile devices (industry target < 2.5s).",
    "Missing automated commercial solar ROI/net-metering quotation calculator.",
    "Customer self-service portal is absent; leads rely on manual email/call inquiry.",
    "Outdated WordPress 5.4 installation poses critical security vulnerabilities."
  ]
}
```
This structured audit directly arms Agent 1's outreach generator with grounded, irrefutable technical facts to craft highly customized consulting proposals.

