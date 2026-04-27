import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    host: true,
  },
  build: {
    // maplibre-gl ships as a large prebuilt ESM bundle; keep it isolated and
    // raise the warning threshold so build noise tracks actual regressions.
    chunkSizeWarningLimit: 1100,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) {
            return undefined;
          }
          if (id.includes("maplibre-gl")) {
            return "maplibre";
          }
          if (id.includes("react") || id.includes("scheduler")) {
            return "react-vendor";
          }
          return undefined;
        },
      },
    },
  },
});
