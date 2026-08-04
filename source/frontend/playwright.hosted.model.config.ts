import { defineConfig } from "@playwright/test";
import hostedConfig from "./playwright.hosted.config";

export default defineConfig({
  ...hostedConfig,
  testMatch: "hosted.model-fetch.spec.ts",
  timeout: 10 * 60_000,
});
