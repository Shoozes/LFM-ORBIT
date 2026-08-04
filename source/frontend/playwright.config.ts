import { defineConfig } from "@playwright/test";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { API_BASE, API_HEALTH_URL, APP_BASE, DEBUG_BASE } from "./e2e/testUrls";

const reuseExistingServer = process.env.PLAYWRIGHT_REUSE_SERVER === "1";
const frontendDir = path.dirname(fileURLToPath(import.meta.url));
const backendVenvName = process.platform === "win32"
  ? ".venv-windows"
  : process.platform === "darwin"
    ? ".venv-macos"
    : ".venv-linux";
const backendVenvDir = process.env.UV_PROJECT_ENVIRONMENT ?? path.resolve(frontendDir, "../backend", backendVenvName);
const uvCacheDir = path.resolve(frontendDir, "../../runtime-data/tools/uv-cache");
const backendEnv = {
  UV_PROJECT_ENVIRONMENT: backendVenvDir,
  UV_CACHE_DIR: process.env.UV_CACHE_DIR ?? uvCacheDir,
};
const localUvPath = process.platform === "win32"
  ? path.resolve(frontendDir, "../../runtime-data/tools/uv-venv/Scripts/uv.exe")
  : path.resolve(frontendDir, "../../runtime-data/tools/uv-venv/bin/uv");
const uvCommand = process.env.UV_COMMAND
  ?? (existsSync(localUvPath) ? `"${localUvPath}"` : "uv");

export default defineConfig({
  testDir: "./e2e",
  testIgnore: [
    "**/demos/**",
    "**/capture_screenshots.spec.ts",
    "**/dual_agent_demo.spec.ts",
    "**/hosted.build.spec.ts",
    "**/hosted.model-build.spec.ts",
    "**/hosted.model-fetch.spec.ts",
    "**/hosted.pages.spec.ts",
    "**/hosted.pages.live.spec.ts",
    "**/hosted.pages.live.static.spec.ts",
    "**/tutorial_video.spec.ts",
  ],
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [["html", { open: "never" }], ["list"]],
  timeout: 60_000,
  expect: {
    timeout: 15_000,
  },
  use: {
    baseURL: APP_BASE,
    trace: "on-first-retry",
    screenshot: "on",
    video: "retain-on-failure",
    launchOptions: {
      args: [
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--use-gl=swiftshader",
        "--enable-webgl",
        "--ignore-gpu-blocklist",
        "--enable-unsafe-swiftshader",
      ],
    },
  },
  projects: [
    {
      name: "chromium",
      use: {
        browserName: "chromium",
        viewport: { width: 1440, height: 900 },
      },
    },
  ],
  webServer: [
    {
      command: `cd ../backend && ${uvCommand} run --locked uvicorn api.main:app --host 127.0.0.1 --port ${new URL(API_BASE).port}`,
      url: API_HEALTH_URL,
      timeout: 60_000,
      reuseExistingServer,
      env: {
        ...backendEnv,
        RESET_RUNTIME_STATE_ON_BOOT: "true",
        OBSERVATION_PROVIDER: "simsat_sentinel",
        DISABLE_EXTERNAL_APIS: "true",
        ORBIT_CORS_ALLOW_ORIGINS: APP_BASE,
      },
    },
    {
      command: `cd ../backend && ${uvCommand} run --locked uvicorn satellite_debug:app --host 127.0.0.1 --port ${new URL(DEBUG_BASE).port}`,
      url: DEBUG_BASE,
      timeout: 60_000,
      reuseExistingServer,
      env: backendEnv,
    },
    {
      command: `npm run dev -- --host 127.0.0.1 --port ${new URL(APP_BASE).port}`,
      url: APP_BASE,
      timeout: 60_000,
      reuseExistingServer,
      env: {
        VITE_API_BASE_URL: API_BASE,
      },
    },
  ],
});
