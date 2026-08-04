import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

function resolvePublicBase(mode: string, configuredBase?: string): string {
  const fallback = mode === "pages" ? "/LFM-ORBIT/" : "/";
  const base = configuredBase?.trim() || fallback;
  if (base === "/") return base;
  if (!/^\/[A-Za-z0-9._~-]+(?:\/[A-Za-z0-9._~-]+)*\/$/.test(base)) {
    throw new Error("VITE_PUBLIC_BASE must be / or a slash-delimited relative base path ending in /.");
  }
  return base;
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "VITE_");
  const isHostedBuild = mode === "hosted" || mode === "pages";
  const publicBase = resolvePublicBase(mode, env.VITE_PUBLIC_BASE);

  return {
    plugins: [
      react(),
      tailwindcss(),
      {
        name: "orbit-hosted-entry",
        transformIndexHtml: {
          order: "pre",
          handler(html: string) {
            return isHostedBuild ? html.replace("%BASE_URL%main.tsx", "/hosted-main.tsx") : html;
          },
        },
      },
    ],
    base: publicBase,
    server: {
      port: 5173,
      host: true,
    },
    build: {
      outDir: mode === "hosted" ? "dist-hosted" : mode === "pages" ? "dist-pages" : "dist",
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
  };
});
