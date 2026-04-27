import { test, expect } from "@playwright/test";
import { gotoApp, openMapContextMenu, resetRuntimeState } from "./runtime";

test.describe("Bounding Box Draw Validation", () => {
  test("assigning a bbox from the map populates mission focus controls", async ({ page }) => {
    await gotoApp(page);

    await page.waitForTimeout(3_000);
    await openMapContextMenu(page);
    await expect(page.getByText("Spatial Options")).toBeVisible({ timeout: 5_000 });
    await page.getByText("◫ Set Mission BBox Here").click();

    await expect(page.getByRole("button", { name: "View Timelapse Preview" })).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(/\[-?\d+\.\d+, -?\d+\.\d+, -?\d+\.\d+, -?\d+\.\d+\]/)).toBeVisible();
  });

  test("map actions button opens spatial options without right click", async ({ page }) => {
    await gotoApp(page);
    await expect(page.locator(".maplibregl-canvas")).toBeVisible({ timeout: 10_000 });

    const mapActionsButton = page.getByRole("button", { name: "Open spatial options at map center" });
    await expect(mapActionsButton).toBeEnabled({ timeout: 10_000 });
    await mapActionsButton.click();
    await expect(page.getByText("Spatial Options")).toBeVisible({ timeout: 5_000 });

    await page.keyboard.press("Escape");
    await expect(page.getByText("Spatial Options")).toBeHidden();

    await mapActionsButton.click();
    await page.getByText("◫ Set Mission BBox Here").click();

    await expect(page.getByRole("button", { name: "View Timelapse Preview" })).toBeVisible({ timeout: 10_000 });
  });

  test("mission form shows date validation errors before deployment", async ({ page, request }) => {
    await resetRuntimeState(request);
    await gotoApp(page);
    await page.locator("[data-testid='tab-mission']").click();

    await page.getByPlaceholder(/Search for areas/).fill("Detect temporal edge case validation.");
    await page.locator('input[type="date"]').first().fill("2025-06-01");
    await page.locator('input[type="date"]').nth(1).fill("2024-06-01");
    await page.getByRole("button", { name: "Launch Mission" }).click();

    await expect(page.getByText("Start date must be on or before end date.")).toBeVisible();
  });
});
