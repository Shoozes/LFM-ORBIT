import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "hosted.model-build.spec.ts",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [["html", { open: "never" }], ["list"]],
  timeout: 10 * 60_000,
  use: {
    baseURL: "http://127.0.0.1:5178",
    trace: "on-first-retry",
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
  webServer: {
    command: "npm run preview:hosted -- --host 127.0.0.1 --port 5178 --strictPort",
    url: "http://127.0.0.1:5178/",
    timeout: 60_000,
    reuseExistingServer: false,
  },
});
