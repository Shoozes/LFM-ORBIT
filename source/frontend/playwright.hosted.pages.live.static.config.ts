import { defineConfig, devices } from "@playwright/test";

const hostedPagesUrl = process.env.HOSTED_PAGES_URL;
if (!hostedPagesUrl) {
  throw new Error("HOSTED_PAGES_URL is required for the deployed Pages static smoke test");
}

export default defineConfig({
  testDir: "./e2e",
  testMatch: "hosted.pages.live.static.spec.ts",
  outputDir: "test-results/hosted-pages-live-static",
  reporter: [["list"], ["html", { outputFolder: "playwright-report/hosted-pages-live-static", open: "never" }]],
  use: {
    baseURL: hostedPagesUrl,
    ...devices["Desktop Chrome"],
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
});
