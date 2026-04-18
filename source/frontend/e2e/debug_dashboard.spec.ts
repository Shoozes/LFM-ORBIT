import { test, expect } from "@playwright/test";

test.describe("Satellite 8080 Debug Internal Dashboard", () => {
  // Use the 8080 base URL explicitly for this exact test
  test.use({ baseURL: 'http://localhost:8080' });

  test("loads the dynamic satellite queue stats", async ({ page }) => {
    // Attempt navigation to the 8080 uvicorn host
    await page.goto("/");
    
    // Validate core title exists 
    await expect(page.locator("h1")).toContainText("SATELLITE PRUNER ORIN DASHBOARD");
    
    // Ensure the bus history logic doesn't crash
    await expect(page.locator("text=Total Bus History:")).toBeVisible();
    
    // Capture visual snapshot 
    await page.screenshot({ path: "e2e/screenshots/satellite-debug-dashboard.png" });
  });
});
