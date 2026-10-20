# AgentDesk Backend Microservice

AgentDesk's local FastAPI backend provides lead research orchestration, modular provider integration, Playwright web automation, and dataset export.

## Architecture

- **Framework**: FastAPI (async ASGI service running on `http://127.0.0.1:8000`)
- **Research Providers**:
  - `MockResearchProvider` (`mock-demo-provider`): Deterministic simulated records tailored by sector profile, with explicit demo labels and disclaimers.
  - `PlaywrightResearchProvider` (`playwright-live-provider`): Headless Chromium automation for user-supplied target URLs. Respects `robots.txt`, enforces polite request rate limits, and extracts visible metadata (company name, description, visible business emails) without fabricating unverified fields.
- **Export Engine**: RFC 4180 CSV serializer capturing ID, company, contact, email, website, source URL, visible description, and verified field tags.
- **Safety Boundaries**:
  - Does NOT attempt to bypass CAPTCHAs, paywalls, or login protections.
  - Skips disallowed pages in accordance with `robots.txt`.
  - Zero autonomous outbound email transmission.

## Running the Backend

Launch with the local PowerShell launcher or npm script:
```powershell
.\start-backend.ps1
```
or
```bash
npm run backend
```

## Running Tests

Run the backend test suite (unit tests and offline fixture HTML extractions):
```bash
python -m pytest backend/tests -v
```
