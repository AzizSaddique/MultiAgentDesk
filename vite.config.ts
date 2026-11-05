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
        if (req.url === "/__agentdesk_auth_token") {
          const tokenFile = path.resolve(__dirname, "storage/.session_token");
          if (fs.existsSync(tokenFile)) {
            const token = fs.readFileSync(tokenFile, "utf-8").trim();
            res.setHeader("Content-Type", "application/json");
            res.end(JSON.stringify({ token }));
            return;
          }
          res.statusCode = 404;
          res.setHeader("Content-Type", "application/json");
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
