import { test, expect } from "@playwright/test";

test.describe("VLM Grounds E2E visual test", () => {
  test("mounts VLM panel, sets bbox via context menu, executes search", async ({ page }) => {
    await page.goto("/");
    
    // Await map load
    await page.waitForTimeout(1500);

    // Right-click the map canvas to trigger context menu and assign a BBox
    const viewportSize = page.viewportSize() || { width: 1280, height: 720 };
    await page.mouse.click(viewportSize.width / 2 + 100, viewportSize.height / 2 + 100, { button: "right" });
    
    // Click the Context Menu item
    await page.locator('text=◫ Set Mission BBox Here').click();
    
    // Close Mission Control modal if it appears
    await page.locator('button[aria-label="Close"]').click({ force: true }).catch(() => {});
    await page.waitForTimeout(500);
    
    // Press the VLM Vision button
    await page.locator('button[id="vlm-vision-btn"]').click({ force: true });
    
    // VLM Panel should unfold out of the top right
    await expect(page.locator("text=VLM VISION")).toBeVisible();
    
    // Wait for the Grounding input to mount (since activeBbox is now populated)
    const gInput = page.getByPlaceholder('Find: large airplane (lower-left)');
    await expect(gInput).toBeVisible({ timeout: 5000 });
    
    // Issue Grounding Search
    await gInput.fill("Find airplanes");
    await gInput.press("Enter");
    
    // Wait for mock json bounding coordinates to resolve in the UI
    await expect(page.locator('pre').filter({ hasText: /"label":\s*"airplane"/ }).first()).toBeVisible({ timeout: 5000 });
    
    // Issue VQA question
    const vqaInput = page.getByPlaceholder('How many large planes are visible?');
    await vqaInput.fill("How many airplanes");
    await vqaInput.press("Enter");
    await expect(page.locator("p").filter({ hasText: "3" }).first()).toBeVisible({ timeout: 5000 });
    
    // Issue Captioning task
    await page.locator("button:has-text('GENERATE')").click();
    await expect(page.locator("p").filter({ hasText: /airport tarmac|dense canopy|Deforested clearing/ }).first()).toBeVisible({ timeout: 5000 });

    // Capture visual QA proof of work
    await page.screenshot({ path: "e2e/screenshots/vlm-panel-results.png" });
  });
});
