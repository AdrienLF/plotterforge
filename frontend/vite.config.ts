import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";

// Built assets are served by Flask from web/static/app, hence the base path.
// During `npm run dev`, /api is proxied to the Flask server.
export default defineConfig({
  plugins: [svelte()],
  base: "/static/app/",
  build: {
    outDir: "../web/static/app",
    emptyOutDir: true,
  },
  server: {
    proxy: {
      "/api": process.env.VITE_API || "http://127.0.0.1:7438",
    },
  },
});
