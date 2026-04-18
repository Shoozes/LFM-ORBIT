import { test, expect } from "@playwright/test";

test.describe("QA Verification — Single Page Architecture", () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the main page
    await page.goto("http://localhost:5173/");
  });

  test("verify all major panels render correctly", async ({ page }) => {
    // 1. Mission Control
    await expect(page.locator("h2", { hasText: /Mission Control/i })).toBeVisible();
    await expect(page.getByPlaceholder("Search for areas")).toBeVisible();
    
    // 2. Working Conversation
    await expect(page.locator("h2", { hasText: /Working Conversation/i })).toBeVisible();
    await expect(page.getByPlaceholder("Inject operator message")).toBeVisible();
    
    // 3. Ground Agent Assistant
    await expect(page.locator("h2", { hasText: /Ground Agent Assistant/i })).toBeVisible();
    await expect(page.getByPlaceholder("Command agent...")).toBeVisible();
    
    // 4. System Logs & Alerts
    await expect(page.locator("h2", { hasText: /System Logs & Alerts/i })).toBeVisible();
    
    // 5. Provider Settings
    await expect(page.locator("h2", { hasText: /Provider Settings/i })).toBeVisible();
    await expect(page.getByPlaceholder("Sentinel Client ID")).toBeVisible();
  });

  test("verify empty and disabled states", async ({ page }) => {
    // Mission Control Launch should be disabled when empty
    const launchBtn = page.getByRole("button", { name: /Launch Mission/i });
    await expect(launchBtn).toBeVisible();
    await expect(launchBtn).toBeDisabled();

    // Settings save should be disabled automatically
    const saveSettingsBtn = page.getByRole("button", { name: /SAVE CREDENTIALS/i });
    await expect(saveSettingsBtn).toBeVisible();
    await expect(saveSettingsBtn).toBeDisabled();
    
    // Logs empty state
    await expect(page.getByText("No alerts downlinked yet.")).toBeVisible();
  });

  test("verify Mission Control text entry and Launch behavior", async ({ page }) => {
    await page.fill('textarea[placeholder*="Search for areas"]', "Detect canopy loss");
    
    const launchBtn = page.getByRole("button", { name: /Launch Mission/i });
    await expect(launchBtn).toBeEnabled();
    
    // If we click launch, it should say Deploying... or Mission in Progress (if API mock allows)
    // However, without a real backend responding properly, we verify the button was enabled correctly.
  });

  test("verify Ground Agent message input", async ({ page }) => {
    const chatInput = page.getByPlaceholder("Command agent...");
    await chatInput.fill("Start scanning the northern sector");
    
    const sendBtn = page.locator('button:has-text("Send")').nth(1); // Second send button is in GroundAgent
    await sendBtn.click();
    
    // Expect the user message to be reflected instantly
    await expect(page.getByText("Start scanning the northern sector")).toBeVisible();
  });

  test("verify map UI elements load", async ({ page }) => {
    // Expect Map element to be mounted
    await expect(page.locator(".maplibregl-map")).toBeVisible({ timeout: 10_000 });
  });
});
