import { defineConfig } from "@playwright/test";
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
const backendEnv = { UV_PROJECT_ENVIRONMENT: backendVenvDir };

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: [["html", { open: "never" }], ["list"]],
  timeout: 120_000,
  expect: {
    timeout: 20_000,
  },
  use: {
    baseURL: APP_BASE,
    video: "on",
    trace: "on",
    screenshot: "on",
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
      command: `cd ../backend && uv run --no-sync uvicorn api.main:app --host 127.0.0.1 --port ${new URL(API_BASE).port}`,
      url: API_HEALTH_URL,
      timeout: 60_000,
      reuseExistingServer,
      env: {
        ...backendEnv,
        RESET_RUNTIME_STATE_ON_BOOT: "true",
        RUN_AGENT_PAIR_ON_BOOT: "false",
        OBSERVATION_PROVIDER: "simsat_sentinel",
        DISABLE_EXTERNAL_APIS: "true",
      },
    },
    {
      command: `cd ../backend && uv run --no-sync uvicorn satellite_debug:app --host 127.0.0.1 --port ${new URL(DEBUG_BASE).port}`,
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
