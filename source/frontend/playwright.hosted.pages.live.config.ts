import { defineConfig } from "@playwright/test";

const hostedPagesUrl = process.env.HOSTED_PAGES_URL?.trim();
if (!hostedPagesUrl) {
  throw new Error("HOSTED_PAGES_URL must be set to run the deployed Pages-origin smoke.");
}

const target = new URL(hostedPagesUrl);
if (!["http:", "https:"].includes(target.protocol) || !target.pathname.endsWith("/")) {
  throw new Error("HOSTED_PAGES_URL must be an HTTP(S) URL with a trailing slash.");
}

export default defineConfig({
  testDir: "./e2e",
  testMatch: "hosted.pages.live.spec.ts",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [["html", { open: "never" }], ["list"]],
  timeout: 10 * 60_000,
  use: {
    baseURL: target.toString(),
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
});
