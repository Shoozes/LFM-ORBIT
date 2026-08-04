import { defineConfig } from "@playwright/test";
import baseConfig from "./playwright.config";

export default defineConfig({
  ...baseConfig,
  testIgnore: [],
  testMatch: [
    "**/capture_screenshots.spec.ts",
    "**/dual_agent_demo.spec.ts",
    "**/tutorial_video.spec.ts",
  ],
  timeout: 120_000,
  use: {
    ...baseConfig.use,
    screenshot: "on",
    video: "on",
  },
});
