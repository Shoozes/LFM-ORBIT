import { test, expect } from "@playwright/test";
import { gotoApp, resetRuntimeState } from "./runtime";

test.describe("QA Verification — Single Page Architecture", () => {
  test.beforeEach(async ({ page, request }) => {
    await resetRuntimeState(request);
    await gotoApp(page);
  });

  test("verify all major panels render correctly", async ({ page }) => {
    // 1. Mission tab
    await page.getByTestId("tab-mission").click();
    await expect(page.getByText("New Mission", { exact: true })).toBeVisible();
    await expect(page.getByTestId("mission-task-input")).toBeVisible();

    // 2. Agents tab
    await page.getByTestId("tab-agents").click();
    await expect(page.getByTestId("header-agent-bus")).toBeVisible();
    await expect(page.getByPlaceholder("Inject manual command into agent bus…")).toBeVisible();
    await expect(page.getByPlaceholder("Command agent...")).toBeVisible();

    // 3. Logs tab
    await page.getByTestId("tab-logs").click();
    await expect(page.getByText("Alerts & Logs")).toBeVisible();

    // 4. Settings tab
    await page.getByTestId("tab-settings").click();
    await expect(page.getByText("Provider Status")).toBeVisible();
    await expect(page.getByPlaceholder("Sentinel Client ID")).toBeVisible();
  });

  test("verify empty and disabled states", async ({ page }) => {
    const launchBtn = page.getByRole("button", { name: /Launch Mission|Mission Complete/i });
    await expect(launchBtn).toBeVisible();
    await expect(launchBtn).toBeDisabled();

    // Settings save should be disabled automatically
    await page.getByTestId("tab-settings").click();
    const saveSettingsBtn = page.getByRole("button", { name: /save credentials/i });
    await expect(saveSettingsBtn).toBeVisible();
    await expect(saveSettingsBtn).toBeDisabled();

    // Logs state may be empty on boot or already contain early downlinks
    await page.getByTestId("tab-logs").click();
    await expect(async () => {
      const emptyVisible = await page.getByText("No alerts downlinked yet.").isVisible().catch(() => false);
      const alertButtons = await page.locator("[data-testid='alert-button']").count();
      expect(emptyVisible || alertButtons > 0).toBeTruthy();
    }).toPass();
  });

  test("verify Mission Control text entry and Launch behavior", async ({ page }) => {
    await page.getByTestId("tab-mission").click();

    await page.getByTestId("mission-task-input").fill("Detect canopy loss");

    const launchBtn = page.getByRole("button", { name: /Launch Mission|Mission Complete/i });
    await expect(launchBtn).toBeEnabled();
  });

  test("verify Ground Agent message input", async ({ page }) => {
    // Navigate to Agents tab
    await page.getByTestId("tab-agents").click();

    const chatInput = page.getByPlaceholder("Command agent...");
    await chatInput.fill("Start scanning the northern sector");

    const sendBtn = page.locator('button:has-text("Send")');
    await sendBtn.click();

    // Expect the user message to be reflected instantly
    await expect(page.getByText("Start scanning the northern sector")).toBeVisible();
  });

  test("verify Ground Agent surfaces backend errors", async ({ page }) => {
    await page.route("**/api/agent/chat", async (route) => {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ error: "Mock assistant outage" }),
      });
    });

    await page.getByTestId("tab-agents").click();

    const chatInput = page.getByPlaceholder("Command agent...");
    await chatInput.fill("Start fallback analysis");
    await page.getByRole("button", { name: "Send" }).click();

    await expect(page.getByText("Start fallback analysis")).toBeVisible();
    await expect(page.getByText("[Link Error: Mock assistant outage]")).toBeVisible({ timeout: 10_000 });
  });

  test("verify Agent Dialogue surfaces bus failures", async ({ page }) => {
    await page.route("**/api/agent/bus/stats", async (route) => {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ error: "Mock stats outage" }),
      });
    });
    await page.route("**/api/agent/bus/inject", async (route) => {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ error: "Mock bus outage" }),
      });
    });

    await page.getByTestId("tab-agents").click();
    await expect(page.getByText("Bus stats unavailable")).toBeVisible({ timeout: 10_000 });

    const injectInput = page.getByPlaceholder("Inject manual command into agent bus…");
    await injectInput.fill("Check sensor handoff");
    await page.getByRole("button", { name: "Inject" }).click();

    await expect(page.getByText("Mock bus outage")).toBeVisible({ timeout: 10_000 });
  });

  test("verify map UI elements load and LINK OPEN has tooltip", async ({ page }) => {
    // Expect Map element to be mounted
    await expect(page.locator(".maplibregl-map")).toBeVisible({ timeout: 10_000 });

    // Check that LINK OPEN or DISCONNECTED badge exists and has title
    const linkBadge = page.locator('div[title="Telemetry Link Status (View Only)"]');
    await expect(linkBadge).toBeVisible();
  });

  test("verify Draw Area on Map functionality and cancellation", async ({ page }) => {
    await page.getByTestId("tab-mission").click();

    const drawBtn = page.getByRole("button", { name: "Draw Area on Map" });
    await drawBtn.click();

    // Banner should appear
    const banner = page.getByText("DRAWING MODE ACTIVE");
    await expect(banner).toBeVisible();

    // Press escape to cancel
    await page.keyboard.press("Escape");
    await expect(banner).toBeHidden();
  });
});
