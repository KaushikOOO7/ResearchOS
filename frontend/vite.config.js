import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

/**
 * Vite configuration for ResearchOS.
 *
 * The dev server proxies `/api/*` to the FastAPI backend so the browser only
 * ever talks to its own origin — which keeps the app working locally, behind a
 * reverse proxy, and inside hosted preview environments (no CORS surprises, no
 * hardcoded localhost URLs in components).
 */
export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // bind 0.0.0.0 so proxied/preview hosts can reach the server
    port: 5173,
    strictPort: false,
    // Allow proxied preview hostnames (e.g. *.e2b.app). Host checking is a
    // dev-server protection only; production builds are served by a real
    // web server in front of the API.
    allowedHosts: true,
    proxy: {
      "/api": {
        target: process.env.VITE_BACKEND_URL || "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
  preview: {
    host: true,
    port: 4173,
  },
  build: {
    outDir: "dist",
    sourcemap: false,
  },
});
