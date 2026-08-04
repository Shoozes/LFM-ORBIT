import { expect, test } from "@playwright/test";
import { readdir } from "node:fs/promises";
import path from "node:path";

test("hosted production build is static-safe at the root route", async ({ page }) => {
  const forbiddenRequests: string[] = [];
  const scriptMimes: string[] = [];
  page.on("request", (request) => {
    const url = request.url();
    if (/:8000\b|\/api(?:\/|$)|\/ws(?:\/|$)/.test(url)) forbiddenRequests.push(url);
  });
  page.on("response", (response) => {
    if (new URL(response.url()).pathname.endsWith(".js")) {
      scriptMimes.push(response.headers()["content-type"] ?? "");
    }
  });

  await page.goto("/");
  const packageManifest = await page.request.get("/demo-packages/index.json");
  const modelManifest = await page.request.get("/model-manifest.json");
  expect(packageManifest.ok()).toBe(true);
  expect(packageManifest.headers()["content-type"]).toMatch(/application\/json/i);
  expect((await packageManifest.json()).packages).toHaveLength(3);
  expect(modelManifest.ok()).toBe(true);
  expect(modelManifest.headers()["content-type"]).toMatch(/application\/json/i);
  expect((await modelManifest.json()).revision).toMatch(/^[a-f0-9]{40}$/);
  await expect(page.getByRole("heading", { name: /small model turns satellite change/i })).toBeVisible();
  await expect(page.getByRole("img", { name: /Atacama mining region/i })).toBeVisible();
  await expect(page.getByRole("link", { name: /Full app \(local\)/i })).toHaveCount(0);
  await page.getByRole("button", { name: /Ice extent quality gate/i }).click();
  await expect(page.getByRole("img", { name: /Greenland ice and snow/i })).toBeVisible();

  expect(scriptMimes.length).toBeGreaterThan(0);
  expect(scriptMimes.every((mime) => /javascript/i.test(mime))).toBe(true);
  const assetNames = await readdir(path.resolve(process.cwd(), "dist-hosted", "assets"));
  const wasmAsset = assetNames.find((assetName) => assetName.endsWith(".wasm"));
  expect(wasmAsset).toBeTruthy();
  const wasmResponse = await page.request.get(`/assets/${wasmAsset}`);
  expect(wasmResponse.ok()).toBe(true);
  expect(wasmResponse.headers()["content-type"]).toMatch(/application\/wasm/i);
  expect(forbiddenRequests).toEqual([]);
});
