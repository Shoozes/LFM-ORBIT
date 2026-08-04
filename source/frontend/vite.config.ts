import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { resolveHostedModelEnabled } from "./hosted/hostedConfigCore.js";

const frontendRoot = path.dirname(fileURLToPath(import.meta.url));
const hostedModelManifestPath = path.join(frontendRoot, "hosted", "model-manifest.json");

function hostedModelManifestPlugin(enabled: boolean) {
  const manifest = readFileSync(hostedModelManifestPath, "utf8");
  return {
    name: "orbit-hosted-model-manifest",
    configureServer(server: { middlewares: { use: (handler: (request: { url?: string }, response: { statusCode: number; setHeader: (name: string, value: string) => void; end: (body: string) => void }, next: () => void) => void) => void } }) {
      if (!enabled) return;
      server.middlewares.use((request, response, next) => {
        const pathname = new URL(request.url ?? "/", "http://orbit.local").pathname;
        if (!pathname.endsWith("/model-manifest.json")) {
          next();
          return;
        }
        response.statusCode = 200;
        response.setHeader("Content-Type", "application/json; charset=utf-8");
        response.end(manifest);
      });
    },
    generateBundle() {
      if (enabled) {
        this.emitFile({ type: "asset", fileName: "model-manifest.json", source: manifest });
      }
    },
  };
}

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
  const hostedModelEnabled = resolveHostedModelEnabled(mode, env.VITE_HOSTED_MODEL_ENABLED);
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
            if (!isHostedBuild) return html;
            const entry = hostedModelEnabled ? "/hosted-model-main.tsx" : "/hosted-main.tsx";
            return html.replace("%BASE_URL%main.tsx", entry);
          },
        },
      },
      hostedModelManifestPlugin(hostedModelEnabled),
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
