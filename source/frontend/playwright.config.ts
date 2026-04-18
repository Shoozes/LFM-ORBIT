import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
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
    baseURL: "http://localhost:5173",
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
      command: "cd ../backend && uvicorn api.main:app --host 0.0.0.0 --port 8000",
      port: 8000,
      timeout: 60_000,
      reuseExistingServer: true,
      env: { RESET_RUNTIME_STATE_ON_BOOT: "true", OBSERVATION_PROVIDER: "simsat_sentinel", DISABLE_EXTERNAL_APIS: "true" },
    },
    {
      command: "cd ../backend && uvicorn satellite_debug:app --host 0.0.0.0 --port 8080",
      port: 8080,
      timeout: 60_000,
      reuseExistingServer: true,
    },
    {
      command: "npm run dev",
      port: 5173,
      timeout: 60_000,
      reuseExistingServer: true,
    },
  ],
});
