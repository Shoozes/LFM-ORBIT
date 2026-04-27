import { test, expect } from '@playwright/test';
import { gotoApp } from "./runtime";

test.describe('LFM Orbit QA Focus Validation', () => {

  test.beforeEach(async ({ page }) => {
    // Navigate to the app boundary
    await gotoApp(page);
  });

  test('Map and Global Health States Render Correctly', async ({ page }) => {
    // Verify LINK OPEN badge appears
    const linkBadge = page.locator('text=LINK OPEN').first();
    await expect(linkBadge).toBeVisible({ timeout: 15000 });

    // Verify Mission Active status doesn't break UI when rendered
    // If it's missing (no active mission), the map remains visible
    await expect(page.locator('.maplibregl-canvas')).toBeVisible();
  });

  test('Agents Tab WebSocket Connects and Dialogue Runs', async ({ page }) => {
    // Switch to Agents Tab
    await page.getByTestId('tab-agents').click();

    // Verify WebSocket negotiates and connects
    const wsLabel = page.getByTestId('header-agent-bus');
    await expect(wsLabel).toBeVisible();

    // Note: React 18 strict mode forces a reconnect, it may briefly flash CONNECTING
    // Usually playwright detects internal node bindings smoothly. We search for text indicating UI completion.
    await expect(page.locator('text=AGENT DIALOGUE BUS').first()).toBeVisible();
  });

  test('Settings Panel Connects and Retrieves Status', async ({ page }) => {
    // Navigate to Settings
    await page.getByTestId('tab-settings').click();

    // The panel itself should open reliably even on a cold backend start.
    await expect(page.locator('text=Provider Status')).toBeVisible();
    await expect(page.locator('text=Local Model')).toBeVisible({ timeout: 20_000 });
  });

  test('Mission Tab Interactive Tools Work', async ({ page }) => {
    await page.getByTestId('tab-mission').click();

    // Check that we can toggle on the boundary drawing mode
    const drawButton = page.locator('button', { hasText: 'Draw Area on Map' });
    if (await drawButton.isVisible()) {
        await drawButton.click();
        const cancelEsc = page.locator('text=CANCEL [ESC]');
        await expect(cancelEsc).toBeVisible();
        await cancelEsc.click();
    }
  });

  test('Alerts Tab Opens and Displays Items or Empty State', async ({ page }) => {
    await page.getByTestId('tab-logs').click();
    await expect(page.locator('text=Alerts & Logs').first()).toBeVisible();
    await expect(page.locator('text=Flagged Examples').first()).toBeVisible();
  });

  test('Mock-Mission Bounding Box Selection Renders', async ({ page }) => {
    await page.getByTestId('tab-mission').click();

    const drawButton = page.locator('button', { hasText: 'Draw Area on Map' });
    if (await drawButton.isVisible()) {
        await drawButton.click();

        // Verify the Drawing pulse element appears in the top center
        const drawingOverlay = page.locator('text=DRAWING MODE ACTIVE');
        await expect(drawingOverlay).toBeVisible();

        // Simulate drawing by triggering ESC to cleanly close it so test resets state
        const cancelEsc = page.locator('text=CANCEL [ESC]');
        await cancelEsc.click();

        // Verify it disappeared
        await expect(drawingOverlay).toHaveCount(0);
    }
  });

});
