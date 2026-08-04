import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "hosted.capture.spec.ts",
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  timeout: 30_000,
  use: {
    baseURL: "http://127.0.0.1:5175",
    screenshot: "only-on-failure",
    video: "on",
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
    command: "npm run dev -- --host 127.0.0.1 --port 5175 --strictPort",
    url: "http://127.0.0.1:5175/hosted",
    timeout: 60_000,
    reuseExistingServer: false,
  },
});
