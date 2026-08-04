import { expect, test } from "@playwright/test";
import { readdir } from "node:fs/promises";
import path from "node:path";

const PAGES_BASE = process.env.VITE_PUBLIC_BASE ?? "/LFM-ORBIT/";

test("hosted Pages build stays under the project path", async ({ page }) => {
  const firstPartyRootRequests: string[] = [];
  const forbiddenRootRequests: string[] = [];
  const scriptMimes: string[] = [];
  const cssMimes: string[] = [];

  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.origin !== "http://127.0.0.1:5177") return;
    if (!url.pathname.startsWith(PAGES_BASE)) firstPartyRootRequests.push(url.pathname);
    if (/^\/(?:assets|demo-assets|demo-packages|model-manifest\.json|orbit-mark\.svg)(?:\/|$)/.test(url.pathname)) {
      forbiddenRootRequests.push(url.pathname);
    }
  });
  page.on("response", (response) => {
    const pathname = new URL(response.url()).pathname;
    const contentType = response.headers()["content-type"] ?? "";
    if (pathname.endsWith(".js")) scriptMimes.push(contentType);
    if (pathname.endsWith(".css")) cssMimes.push(contentType);
  });

  await page.goto(PAGES_BASE);
  await expect(page.getByRole("heading", { name: /small model turns satellite change/i })).toBeVisible();
  await expect(page.getByRole("link", { name: /Orbit hosted demo home/i })).toHaveAttribute("href", PAGES_BASE);
  await expect(page.getByRole("link", { name: /Full app \(local\)/i })).toHaveCount(0);

  const packageResponse = await page.request.get(new URL("demo-packages/index.json", page.url()).toString());
  const modelResponse = await page.request.get(new URL("model-manifest.json", page.url()).toString());
  expect(packageResponse.ok()).toBe(true);
  expect(packageResponse.headers()["content-type"]).toMatch(/application\/json/i);
  expect(modelResponse.ok()).toBe(true);
  expect(modelResponse.headers()["content-type"]).toMatch(/application\/json/i);

  const packagePayload = await packageResponse.json();
  expect(packagePayload.packages).toHaveLength(3);
  for (const item of packagePayload.packages) {
    expect(item.imageSrc).toMatch(/^demo-assets\//);
    const imageResponse = await page.request.get(new URL(item.imageSrc, page.url()).toString());
    expect(imageResponse.ok()).toBe(true);
    expect(imageResponse.headers()["content-type"]).toMatch(/^image\//i);
  }

  await page.getByRole("button", { name: /Fireline review packet/i }).click();
  await expect(page.getByRole("img", { name: /Southeast US fireline review/i })).toBeVisible();
  await page.getByRole("link", { name: "What it teaches" }).click();
  await expect(page).toHaveURL(/#lesson$/);
  await page.getByRole("link", { name: "Saved evidence" }).click();
  await expect(page).toHaveURL(/#evidence$/);
  await page.getByRole("link", { name: "Fetch model" }).click();
  await expect(page).toHaveURL(/#model$/);

  const assetNames = await readdir(path.resolve(process.cwd(), "dist-pages", "assets"));
  const wasmAsset = assetNames.find((assetName) => assetName.endsWith(".wasm"));
  expect(wasmAsset).toBeTruthy();
  const wasmResponse = await page.request.get(new URL(`assets/${wasmAsset}`, page.url()).toString());
  expect(wasmResponse.ok()).toBe(true);
  expect(wasmResponse.headers()["content-type"]).toMatch(/application\/wasm/i);

  const faviconResponse = await page.request.get(new URL("orbit-mark.svg", page.url()).toString());
  expect(faviconResponse.ok()).toBe(true);
  expect(faviconResponse.headers()["content-type"]).toMatch(/image\/svg/i);
  expect(firstPartyRootRequests).toEqual([]);
  expect(forbiddenRootRequests).toEqual([]);
  expect(scriptMimes.length).toBeGreaterThan(0);
  expect(scriptMimes.every((mime) => /javascript/i.test(mime))).toBe(true);
  expect(cssMimes.length).toBeGreaterThan(0);
  expect(cssMimes.every((mime) => /text\/css/i.test(mime))).toBe(true);
});
