import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies API + WebSocket to the Python backend on :8000.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/runs": { target: "http://localhost:8000", ws: true },
      "/plugins": { target: "http://localhost:8000" },
      "/approvals": { target: "http://localhost:8000" },
      "/health": { target: "http://localhost:8000" },
    },
  },
});
