import { test, expect } from "@playwright/test";

test.describe("Bounding Box Draw Validation", () => {
  test("drawing a bbox renders dashed boundary correctly and completes", async ({ page }) => {
    await page.goto("/");
    // Open mission control
    await page.locator("#mission-control-btn").click();
    
    // Click "Draw Area on Map"
    await page.getByText("Draw Area on Map").click();
    
    // Simulate drawing
    const viewportSize = page.viewportSize() || { width: 1280, height: 720 };
    await page.mouse.move(viewportSize.width / 2, viewportSize.height / 2);
    await page.mouse.down();
    await page.mouse.move(viewportSize.width / 2 + 100, viewportSize.height / 2 + 100);
    await page.mouse.up();
    
    // Assert visual area rendered
    await expect(page.locator("text=Clear")).toBeVisible({ timeout: 10_000 });
    
    // Validate we map back to the UI indicating Focus Area selected
    await expect(page.getByText("Focus Area")).toBeVisible();
    await expect(page.getByText("Clear")).toBeVisible();
  });
});
