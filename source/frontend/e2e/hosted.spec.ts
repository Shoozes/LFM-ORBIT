import { expect, test } from "@playwright/test";

test("hosted demo is usable without the Orbit backend", async ({ page }) => {
  const forbiddenRequests: string[] = [];
  const modelRequests: string[] = [];
  page.on("request", (request) => {
    const url = request.url();
    if (/:8000\b|\/api(?:\/|$)|\/ws(?:\/|$)/.test(url)) forbiddenRequests.push(url);
    if (url.includes("huggingface.co/") && url.endsWith(".gguf")) modelRequests.push(url);
  });
  await page.goto("/hosted");

  await expect(page.getByRole("heading", { name: /small model turns satellite change/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /Fetch the small model/i })).toBeVisible();
  await expect(page.getByText("No Orbit API required")).toBeVisible();
  await expect(page.getByText("219 MB · Q4_0")).toBeVisible();
  await expect(page.getByText("License: mit · Text reasoning only")).toBeVisible();
  expect(modelRequests).toEqual([]);
  await expect(page.getByRole("button", { name: /Ice extent quality gate/i })).toBeVisible();
  await expect(page.getByRole("img", { name: /Atacama mining region/i })).toBeVisible();
  await expect(page.getByTestId("hosted-evidence-provenance")).toContainText("Saved replay");

  await page.getByRole("button", { name: /Ice extent quality gate/i }).click();
  await expect(page.getByRole("heading", { name: "Ice extent quality gate" })).toBeVisible();
  await expect(page.getByText(/cloud rejection/i)).toBeVisible();
  await expect(page.getByRole("img", { name: /Greenland ice and snow/i })).toBeVisible();
  await expect(page.getByRole("link", { name: /Full app \(local\)/i }).first()).toHaveAttribute("href", "/");
  expect(forbiddenRequests).toEqual([]);
});
