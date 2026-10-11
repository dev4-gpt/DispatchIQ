import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

// `/api` is proxied to Developer 1's FastAPI service. `npm run dev:fixture` (mode "fixture")
// switches the client to the clearly labeled in-browser development fixture instead.
export default defineConfig(({ mode }) => ({
  // Relative asset paths so the static demo build works from any folder (repo, Pages, artifact).
  base: "./",
  plugins: [react(), tailwindcss()],
  build: mode === "fixture" ? { rollupOptions: { output: { inlineDynamicImports: true } } } : undefined,
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: { "/api": { target: process.env.DISPATCHIQ_API ?? "http://127.0.0.1:8000", changeOrigin: false } },
  },
}));
