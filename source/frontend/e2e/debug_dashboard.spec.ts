import { test, expect } from "@playwright/test";
import { gotoApp } from "./runtime";
import { DEBUG_BASE } from "./testUrls";

test.describe("Satellite 8080 Debug Internal Dashboard", () => {
  test.use({ baseURL: DEBUG_BASE });

  test("loads the dynamic satellite queue stats", async ({ page }) => {
    await gotoApp(page);

    await expect(page).toHaveTitle(/Orbit Link/i);
    await expect(page.getByText("Orbit Link — Satellite Agent Debug")).toBeVisible();
    await expect(page.getByText("Total Msgs")).toBeVisible();
    await expect(page.getByText("SAT Dispatched")).toBeVisible();
    await expect(page.getByText("Outbound Buffer")).toBeVisible();
    await expect(page.locator("#hb-text")).toBeVisible();

    await page.screenshot({ path: "e2e/screenshots/satellite-debug-dashboard.png" });
  });
});
