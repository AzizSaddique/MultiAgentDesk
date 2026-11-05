# Phase A.2.2 — Vite Dev Token Security Report

**Date:** November 5, 2026  
**Component:** `vite.config.ts` (`authDevPlugin`)  
**Target Vulnerability:** `ADV-SEC-04` (MEDIUM — Vite Development Server Token Exposure via Unrestricted Cross-Origin Access)  
**Status:** REMEDIATED & HARDENED  

---

## 1. Problem Statement & Root Cause (ADV-SEC-04)

During Phase A.2, an authentication helper plugin (`authDevPlugin`) was introduced into Vite's development server (`vite.config.ts`) to enable the frontend running under `npm run dev` to discover the active backend bearer token from `session_token.txt` via `GET /api/dev-token`.

However, the initial implementation contained severe cross-origin security gaps:
```typescript
// INSECURE PATTERN IN PHASE A.2:
res.setHeader('Access-Control-Allow-Origin', '*');
res.setHeader('Content-Type', 'application/json');
res.end(JSON.stringify({ token }));
```
Because the wildcard `*` was permitted and no origin validation was conducted:
1. Any malicious website visited by a developer in Chrome, Firefox, or Edge could execute:
   ```javascript
   fetch("http://localhost:1420/api/dev-token")
     .then(r => r.json())
     .then(data => exfiltrate(data.token));
   ```
2. The browser would permit reading the response because of `Access-Control-Allow-Origin: *`.
3. The stolen session token would allow the attacker's script to make arbitrary authenticated API calls to the local FastAPI backend (`http://localhost:8000/api/*`).

---

## 2. Technical Remediation: Hardened `authDevPlugin`

In `vite.config.ts`, `authDevPlugin` was rewritten with defense-in-depth origin and header enforcement:

```typescript
function authDevPlugin(): Plugin {
  return {
    name: 'agentdesk-dev-auth-helper',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        if (req.url !== '/api/dev-token') {
          return next();
        }

        // 1. Enforce GET method only
        if (req.method !== 'GET') {
          res.statusCode = 405;
          res.end(JSON.stringify({ error: 'Method Not Allowed' }));
          return;
        }

        // 2. Validate Host header against DNS rebinding / host spoofing
        const host = req.headers['host'];
        const allowedHosts = ['localhost:1420', '127.0.0.1:1420'];
        if (!host || !allowedHosts.includes(host)) {
          res.statusCode = 403;
          res.end(JSON.stringify({ error: 'Forbidden: Invalid Host header' }));
          return;
        }

        // 3. Strict Origin Validation
        const origin = req.headers['origin'];
        const allowedOrigins = [
          'http://localhost:1420',
          'http://127.0.0.1:1420',
          'tauri://localhost',
          'http://tauri.localhost',
        ];

        // 4. Sec-Fetch-Site enforcement: block cross-site requests
        const secFetchSite = req.headers['sec-fetch-site'];
        if (secFetchSite === 'cross-site') {
          res.statusCode = 403;
          res.end(JSON.stringify({ error: 'Forbidden: Cross-site access prohibited' }));
          return;
        }

        if (origin && !allowedOrigins.includes(origin)) {
          res.statusCode = 403;
          res.end(JSON.stringify({ error: 'Forbidden: Unauthorized Origin' }));
          return;
        }

        // 5. Read token safely from session_token.txt
        const tokenPath = path.resolve(__dirname, 'session_token.txt');
        if (!fs.existsSync(tokenPath)) {
          res.statusCode = 404;
          res.end(JSON.stringify({ error: 'Session token not found' }));
          return;
        }

        try {
          const token = fs.readFileSync(tokenPath, 'utf8').trim();
          
          // 6. Restrict CORS to exact matching local origin, NEVER wildcard
          const responseOrigin = origin && allowedOrigins.includes(origin) ? origin : 'http://localhost:1420';
          res.setHeader('Access-Control-Allow-Origin', responseOrigin);
          res.setHeader('Vary', 'Origin');
          res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate');
          res.setHeader('Content-Type', 'application/json');
          res.end(JSON.stringify({ token }));
        } catch {
          res.statusCode = 500;
          res.end(JSON.stringify({ error: 'Failed to read session token' }));
        }
      });
    },
  };
}
```

---

## 3. Threat Mitigation Analysis

1. **Malicious Web Page (e.g. `https://evil.com`):**
   - The attacker's browser automatically sets `Origin: https://evil.com` and `Sec-Fetch-Site: cross-site`.
   - The middleware inspects `secFetchSite === 'cross-site'` and `!allowedOrigins.includes(origin)`.
   - Request is aborted with `403 Forbidden`.
   - Browser does not receive the token.
2. **DNS Rebinding against Vite Dev Server:**
   - If an attacker attempts to rebind `localhost:1420` via `attacker.com:1420`, the `Host` header sent by the browser is `attacker.com:1420`.
   - The middleware checks `allowedHosts.includes(host)` and rejects with `403 Forbidden`.
3. **Caching and History Protection:**
   - `Cache-Control: no-store, no-cache, must-revalidate` guarantees the token is never cached by browser disk/memory caches or proxy caches.

---

## 4. Production vs Development Boundaries

- **Development Only:** `authDevPlugin` is configured in Vite's `configureServer` hook. It is active *only* when developers run `npm run dev` / `npm run tauri dev`.
- **Production Build:** When `npm run build` is executed, Vite compiles static assets into `dist/`. The development middleware server does not exist in the production bundle. In production Tauri packages, the Tauri Rust backend passes the token securely to the webview or injects it locally without exposing any local dev server port.

