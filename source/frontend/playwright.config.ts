import { defineConfig } from "@playwright/test";
import { API_BASE, API_HEALTH_URL, APP_BASE, DEBUG_BASE } from "./e2e/testUrls";

const reuseExistingServer = process.env.PLAYWRIGHT_REUSE_SERVER === "1";

export default defineConfig({
  testDir: "./e2e",
  testIgnore: ["**/demos/**"],
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
    video: "on-failure",
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
      env: { RESET_RUNTIME_STATE_ON_BOOT: "true", OBSERVATION_PROVIDER: "simsat_sentinel", DISABLE_EXTERNAL_APIS: "true" },
    },
    {
      command: `cd ../backend && uv run --no-sync uvicorn satellite_debug:app --host 127.0.0.1 --port ${new URL(DEBUG_BASE).port}`,
      url: DEBUG_BASE,
      timeout: 60_000,
      reuseExistingServer,
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
