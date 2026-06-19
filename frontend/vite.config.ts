import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, proxy API + health to the local backend so the SPA is same-origin.
// Override the target with VITE_API_TARGET (default: a local backend on :8000).
const target = process.env.VITE_API_TARGET || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target, changeOrigin: true },
      "/health": { target, changeOrigin: true },
    },
  },
});
