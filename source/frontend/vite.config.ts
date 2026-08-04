import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig(({ mode }) => ({
  plugins: [
    react(),
    tailwindcss(),
    {
      name: "orbit-hosted-entry",
      transformIndexHtml: {
        order: "pre",
        handler(html: string) {
          return mode === "hosted" ? html.replace("/main.tsx", "/hosted-main.tsx") : html;
        },
      },
    },
  ],
  server: {
    port: 5173,
    host: true,
  },
  build: {
    outDir: mode === "hosted" ? "dist-hosted" : "dist",
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
          if (id.includes("@wllama/wllama")) {
            return "wllama";
          }
          if (id.includes("react") || id.includes("scheduler")) {
            return "react-vendor";
          }
          return undefined;
        },
      },
    },
  },
}));
