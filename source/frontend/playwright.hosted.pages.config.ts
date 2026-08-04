import { defineConfig } from "@playwright/test";

const publicBase = process.env.VITE_PUBLIC_BASE ?? "/LFM-ORBIT/";
const previewBaseUrl = `http://127.0.0.1:5177${publicBase}`;

export default defineConfig({
  testDir: "./e2e",
  testMatch: "hosted.pages.spec.ts",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [["html", { open: "never" }], ["list"]],
  timeout: 30_000,
  use: {
    baseURL: previewBaseUrl,
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
    command: "npm run preview:pages -- --host 127.0.0.1 --port 5177 --strictPort",
    url: previewBaseUrl,
    timeout: 60_000,
    reuseExistingServer: false,
  },
});
