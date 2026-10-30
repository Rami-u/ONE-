import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// One dev server serves the main site (http://localhost:5173) and every
// workspace sub-domain (http://{slug}.localhost:5173). Browsers resolve
// *.localhost to the local machine, so no DNS or hosts-file edits are needed.
// The proxy keeps the API same-origin so Django session cookies stay host-only.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // Accept any *.{base domain}.localhost / *.{base domain} hostname.
    allowedHosts: true,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/media": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
});
