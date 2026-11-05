import { defineConfig, Plugin } from "vite";
import react from "@vitejs/plugin-react";
import fs from "node:fs";
import path from "node:path";

// @ts-expect-error process is a nodejs global
const host = process.env.TAURI_DEV_HOST;

function authDevPlugin(): Plugin {
  return {
    name: "agentdesk-auth-dev",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = req.url ? req.url.split("?")[0] : "";
        if (url === "/__agentdesk_auth_token") {
          // 1. Only allow GET requests
          if (req.method !== "GET") {
            res.statusCode = 405;
            res.setHeader("Content-Type", "application/json");
            res.end(JSON.stringify({ error: "Method not allowed" }));
            return;
          }

          // 2. Validate Host header
          const hostHeader = (req.headers.host || "").toLowerCase();
          const allowedHosts = ["localhost:1420", "127.0.0.1:1420"];
          if (!allowedHosts.includes(hostHeader)) {
            res.statusCode = 403;
            res.setHeader("Content-Type", "application/json");
            res.end(JSON.stringify({ error: "Forbidden: invalid host" }));
            return;
          }

          // 3. Validate Origin header if present (block cross-origin access)
          const origin = req.headers.origin;
          const allowedOrigins = [
            "http://localhost:1420",
            "http://127.0.0.1:1420",
            "tauri://localhost",
            "https://tauri.localhost",
          ];

          if (origin && !allowedOrigins.includes(origin)) {
            res.statusCode = 403;
            res.setHeader("Content-Type", "application/json");
            res.end(JSON.stringify({ error: "Forbidden: unauthorized origin" }));
            return;
          }

          // 4. Validate Sec-Fetch-Site (block cross-site fetches)
          const secFetchSite = req.headers["sec-fetch-site"];
          if (secFetchSite && secFetchSite !== "same-origin" && secFetchSite !== "none") {
            res.statusCode = 403;
            res.setHeader("Content-Type", "application/json");
            res.end(JSON.stringify({ error: "Forbidden: cross-site request" }));
            return;
          }

          // 5. Read token file safely
          const tokenFile = path.resolve(__dirname, "storage/.session_token");
          if (fs.existsSync(tokenFile)) {
            try {
              const token = fs.readFileSync(tokenFile, "utf-8").trim();
              if (token && token.length >= 32) {
                // Set explicit non-wildcard headers
                if (origin && allowedOrigins.includes(origin)) {
                  res.setHeader("Access-Control-Allow-Origin", origin);
                } else {
                  res.setHeader("Access-Control-Allow-Origin", "http://localhost:1420");
                }
                res.setHeader("Vary", "Origin");
                res.setHeader("Cache-Control", "no-store, no-cache, must-revalidate");
                res.setHeader("X-Content-Type-Options", "nosniff");
                res.setHeader("Content-Type", "application/json");
                res.end(JSON.stringify({ token }));
                return;
              }
            } catch {
              // Fall through to 500
            }
          }

          res.statusCode = 404;
          res.setHeader("Content-Type", "application/json");
          res.setHeader("Cache-Control", "no-store");
          res.end(JSON.stringify({ error: "Token not found" }));
          return;
        }
        next();
      });
    },
  };
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), authDevPlugin()],
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
    host: host || false,
    hmr: host
      ? {
          protocol: "ws",
          host,
          port: 1421,
        }
      : undefined,
    watch: {
      // Tell vite to ignore watching src-tauri
      ignored: ["**/src-tauri/**"],
    },
  },
});
