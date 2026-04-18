/**
 * Screenshot capture spec for README documentation.
 * Captures: satellite agent heartbeat, agent dialogue bus, alert analysis, provider settings.
 * Run with: npx playwright test capture_screenshots.spec.ts --headed
 */
import { test, expect, type Page } from "@playwright/test";

const SHOT_DIR = "e2e/screenshots";

async function waitForAgentDialogue(page: Page) {
  await expect(page.getByText("Agent Dialogue Bus").first()).toBeVisible({ timeout: 15_000 });
}

async function waitForLinkOpen(page: Page) {
  // connection state might take time or fail in some test envs, just wait 3s
  await page.waitForTimeout(3000);
}

async function waitForAlerts(page: Page, min = 1) {
  await page.locator("[data-testid='tab-logs']").click();
  await expect(page.locator("[data-testid='alert-button']").first()).toBeVisible({ timeout: 45_000 });
  const count = await page.locator("[data-testid='alert-button']").count();
  expect(count).toBeGreaterThanOrEqual(min);
}

// ── 1. Satellite Agent Heartbeat ────────────────────────────────────────────

test("screenshot: satellite agent heartbeat + scan HUD", async ({ page }) => {
  test.setTimeout(90_000);
  await page.goto("/");
  await waitForLinkOpen(page);

  // Open agent dialogue tab so heartbeat messages are visible
  await page.locator("[data-testid='tab-agents']").click();
  await waitForAgentDialogue(page);

  // Let a few heartbeat cycles accumulate
  await page.waitForTimeout(12_000);

  await page.screenshot({
    path: `${SHOT_DIR}/01-satellite-heartbeat.png`,
    fullPage: false,
  });
});

// ── 2. Agent Chat Bus — SAT ↔ GND dialogue ─────────────────────────────────

test("screenshot: dual agent dialogue in flight", async ({ page }) => {
  test.setTimeout(90_000);
  await page.goto("/");
  await waitForLinkOpen(page);

  // Launch a mission so agents start talking
  await page.locator("[data-testid='tab-mission']").click();
  await page.waitForTimeout(500);
  await page.getByText("Draw Area on Map").click();

  const vp = page.viewportSize() || { width: 1440, height: 900 };
  await page.mouse.move(vp.width / 2 - 80, vp.height / 2 - 60);
  await page.mouse.down();
  await page.mouse.move(vp.width / 2 + 80, vp.height / 2 + 60, { steps: 20 });
  await page.mouse.up();
  await page.waitForTimeout(500);

  await page.fill("textarea", "Scan this region for recent clear-cut deforestation.");
  await page.getByText("Launch Mission").click();

  // Switch to agent dialogue tab
  await page.locator("[data-testid='tab-agents']").click();
  await waitForAgentDialogue(page);

  // Give agents time to exchange flags and acks
  await page.waitForTimeout(20_000);

  await page.screenshot({
    path: `${SHOT_DIR}/02-agent-dialogue-bus.png`,
    fullPage: false,
  });
});

// ── 3. Alert with temporal evidence + analysis result ──────────────────────

test("screenshot: alert analysis — offline LFM verdict", async ({ page }) => {
  test.setTimeout(90_000);
  await page.goto("/");
  await waitForLinkOpen(page);
  await waitForAlerts(page, 1);

  const firstAlert = page.locator("[data-testid='alert-button']").first();
  await firstAlert.click();

  await expect(
    page.getByText("Before Window", { exact: true })
  ).toBeVisible({ timeout: 8_000 });

  // Run the offline analysis
  await page.locator("[data-testid='analyze-button']").click();
  await expect(page.getByText("offline_lfm_v1")).toBeVisible({ timeout: 15_000 });

  await page.waitForTimeout(1_000);
  await page.screenshot({
    path: `${SHOT_DIR}/03-alert-analysis-verdict.png`,
    fullPage: false,
  });
});

// ── 4. Settings — provider status + local model ────────────────────────────

test("screenshot: settings panel — provider + local model status", async ({ page }) => {
  test.setTimeout(30_000);
  await page.goto("/");
  await page.locator("[data-testid='tab-settings']").click();

  await expect(page.getByText("Provider Status")).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText("Fallback Order")).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText("Local Model")).toBeVisible({ timeout: 10_000 });

  await page.waitForTimeout(500);
  await page.screenshot({
    path: `${SHOT_DIR}/04-settings-provider-model.png`,
    fullPage: false,
  });
});

// ── 5. Full app with scan in progress ──────────────────────────────────────

test("screenshot: full mission control — scan in progress", async ({ page }) => {
  test.setTimeout(90_000);
  await page.goto("/");
  await waitForLinkOpen(page);
  await waitForAlerts(page, 2);
  await page.locator("[data-testid='tab-mission']").click();
  await page.waitForTimeout(2_000);
  await page.screenshot({
    path: `${SHOT_DIR}/05-mission-control-scanning.png`,
    fullPage: false,
  });
});
