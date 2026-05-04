/**
 * Screenshot capture spec for local review and selected README documentation.
 * Captures: satellite agent heartbeat, agent dialogue bus, alert analysis, provider settings.
 * Run with: npx playwright test capture_screenshots.spec.ts --headed
 */
import { test, expect, type Page } from "@playwright/test";
import {
  gotoApp,
  loadSeededReplay,
  resetRuntimeState,
  waitForBasemapReady,
  waitForLinkOpen,
  waitForNextPaint,
} from "./runtime";

const SHOT_DIR = "e2e/screenshots";

async function waitForAgentDialogue(page: Page) {
  await expect(page.getByTestId("header-agent-bus")).toContainText("SAT/GND Dialogue Bus", { timeout: 15_000 });
  await expect(page.getByTestId("agent-bus-status")).toContainText(/open/i, { timeout: 15_000 });
}

async function settleScreenshotFrame(page: Page) {
  await waitForNextPaint(page, 3);
}

async function waitForAlerts(page: Page, min = 1) {
  await page.locator("[data-testid='tab-logs']").click();
  await expect(page.locator("[data-testid='alert-button']").first()).toBeVisible({ timeout: 45_000 });
  const count = await page.locator("[data-testid='alert-button']").count();
  expect(count).toBeGreaterThanOrEqual(min);
}

// ── 1. Satellite Agent Heartbeat ────────────────────────────────────────────

test("screenshot: satellite agent heartbeat + scan HUD", async ({ page, request }) => {
  test.setTimeout(90_000);
  await resetRuntimeState(request);
  await gotoApp(page);
  await waitForLinkOpen(page);
  await waitForBasemapReady(page);

  // Open agent dialogue tab so heartbeat messages are visible
  await page.locator("[data-testid='tab-agents']").click();
  await waitForAgentDialogue(page);

  await expect(page.getByText(/heartbeat/i).first()).toBeVisible({ timeout: 15_000 });
  await settleScreenshotFrame(page);

  await page.screenshot({
    path: `${SHOT_DIR}/01-satellite-heartbeat.png`,
    fullPage: false,
  });
});

// ── 2. Agent Chat Bus — SAT ↔ GND dialogue ─────────────────────────────────

test("screenshot: dual agent dialogue in flight", async ({ page, request }) => {
  test.setTimeout(90_000);
  await resetRuntimeState(request);
  await loadSeededReplay(request);
  await gotoApp(page);
  await waitForLinkOpen(page);
  await waitForBasemapReady(page);

  // Switch to agent dialogue tab
  await page.locator("[data-testid='tab-agents']").click();
  await waitForAgentDialogue(page);
  await expect(page.getByText("Historical replay trace loaded")).toBeVisible({ timeout: 15_000 });

  await page.screenshot({
    path: `${SHOT_DIR}/02-agent-dialogue-bus.png`,
    fullPage: false,
  });
});

// ── 3. Alert with temporal evidence + analysis result ──────────────────────

test("screenshot: alert analysis — offline LFM verdict", async ({ page, request }) => {
  test.setTimeout(90_000);
  await resetRuntimeState(request);
  await loadSeededReplay(request);
  await gotoApp(page);
  await waitForLinkOpen(page);
  await waitForBasemapReady(page);
  await waitForAlerts(page, 1);

  const firstAlert = page.locator("[data-testid='alert-button']").first();
  await firstAlert.click();

  await expect(
    page.getByText("Before Window", { exact: true })
  ).toBeVisible({ timeout: 8_000 });

  // Run the offline analysis
  await page.locator("[data-testid='analyze-button']").click();
  await expect(page.getByText("offline_lfm_v1", { exact: true }).first()).toBeVisible({ timeout: 30_000 });

  await page.getByText("AI Analysis", { exact: true }).evaluate((element) => {
    element.scrollIntoView({ block: "start", inline: "nearest" });
  });
  await settleScreenshotFrame(page);
  await page.screenshot({
    path: `${SHOT_DIR}/03-alert-analysis-verdict.png`,
    fullPage: false,
  });
});

// ── 4. Settings — provider status + local model ────────────────────────────

test("screenshot: settings panel — provider + local model status", async ({ page, request }) => {
  test.setTimeout(30_000);
  await page.setViewportSize({ width: 1440, height: 1040 });
  await resetRuntimeState(request);
  await gotoApp(page);
  await waitForLinkOpen(page);
  await waitForBasemapReady(page);
  await page.locator("[data-testid='tab-settings']").click();

  await expect(page.getByText("Provider Status")).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText("Local Model")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("Model Tiers")).toBeVisible({ timeout: 20_000 });

  await settleScreenshotFrame(page);
  await page.screenshot({
    path: `${SHOT_DIR}/04-settings-provider-model.png`,
    fullPage: false,
  });
});

// ── 5. Full app with scan in progress ──────────────────────────────────────

test("screenshot: full mission control — replay ready", async ({ page, request }) => {
  test.setTimeout(90_000);
  await resetRuntimeState(request);
  await loadSeededReplay(request);
  await gotoApp(page);
  await waitForLinkOpen(page);
  await waitForBasemapReady(page);
  await page.locator("[data-testid='tab-mission']").click();
  await expect(page.getByText("Replay Mission · rondonia_frontier_showcase")).toBeVisible({ timeout: 15_000 });
  await page.screenshot({
    path: `${SHOT_DIR}/05-mission-control-scanning.png`,
    fullPage: false,
  });
});

// ── 6. Ground Agent chat-driven operation proposal ─────────────────────────

test("screenshot: Ground Agent operator playbook", async ({ page, request }) => {
  test.setTimeout(60_000);
  await page.setViewportSize({ width: 1440, height: 1400 });
  await resetRuntimeState(request);
  await gotoApp(page);
  await waitForLinkOpen(page);
  await waitForBasemapReady(page);
  await page.locator("[data-testid='tab-agents']").click();
  await waitForAgentDialogue(page);
  await expect(page.getByTestId("agent-role-strip")).toContainText("Satellite Pruner");
  await expect(page.getByTestId("ground-agent-operator-playbook")).toContainText("Operator Playbook");

  await page.screenshot({
    path: "../../docs/media/readme/readme-ground-agent-playbook.png",
    fullPage: false,
  });
});

test("screenshot: Ground Agent proposes wildfire replay from chat", async ({ page, request }) => {
  test.setTimeout(60_000);
  await page.setViewportSize({ width: 1440, height: 1600 });
  await resetRuntimeState(request);
  await gotoApp(page);
  await waitForLinkOpen(page);
  await waitForBasemapReady(page);
  await page.locator("[data-testid='tab-agents']").click();
  await waitForAgentDialogue(page);

  const chatInput = page.getByPlaceholder("Request replay, mission pack, link action...");
  await chatInput.fill("replay a wildfire mission");
  await page.getByRole("button", { name: "Send" }).click();

  const userMessage = page
    .getByTestId("ground-agent-message-user")
    .filter({ hasText: "replay a wildfire mission" });
  const proposal = page.getByTestId("ground-agent-proposal-card");
  await expect(proposal).toBeVisible({ timeout: 15_000 });
  await expect(userMessage).toBeVisible();
  await expect(proposal.getByText("Load replay: Highway 82 Wildfire Candidate Replay")).toBeVisible();
  await expect(proposal.getByText("georgia_wildfire_replay")).toBeVisible();
  await expect(proposal.getByText("replay a wildfire mission")).toBeVisible();
  await expect(proposal.getByText("cached_api")).toBeVisible();
  await expect(proposal.getByText("State Impact")).toBeVisible();
  await expect(proposal.getByRole("button", { name: "Run Replay" })).toBeVisible();
  await proposal.evaluate((element) => {
    element.scrollIntoView({ block: "center", inline: "nearest" });
  });
  await settleScreenshotFrame(page);

  await page.screenshot({
    path: "../../docs/media/readme/readme-ground-agent-chat-action.png",
    fullPage: false,
  });

  await page.getByTestId("ground-agent-run-proposal").click();
  await expect(page.getByText("Loaded replay `georgia_wildfire_replay`")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("load replay - georgia_wildfire_replay")).toBeVisible({ timeout: 10_000 });
});

test("screenshot: Ground Agent semantic location camera context", async ({ page, request }) => {
  test.setTimeout(60_000);
  await page.setViewportSize({ width: 1440, height: 1100 });
  await resetRuntimeState(request);
  await gotoApp(page);
  await waitForLinkOpen(page);
  await waitForBasemapReady(page);
  await page.locator("[data-testid='tab-agents']").click();
  await waitForAgentDialogue(page);

  const chatInput = page.getByPlaceholder("Request replay, mission pack, link action...");
  await chatInput.fill("cancel the current mission and take us to bull creek fl");
  await page.getByRole("button", { name: "Send" }).click();

  const proposal = page.getByTestId("ground-agent-proposal-card");
  await expect(proposal).toContainText("Bull Creek, FL", { timeout: 15_000 });
  await expect(proposal).toContainText("wetland / pine-flatwoods context");
  await proposal.getByRole("button", { name: "Stop & Fly Map" }).click();

  const hud = page.getByTestId("map-camera-hud");
  await expect(hud).toContainText("Bull Creek, FL", { timeout: 15_000 });
  await expect(hud).toContainText("Terrain:");
  await expect(hud).toContainText("road or trail corridor");
  await expect(page.getByTestId("map-scan-paused-hint")).toBeVisible({ timeout: 15_000 });
  await settleScreenshotFrame(page);

  await page.screenshot({
    path: "../../docs/media/readme/readme-location-camera-context.png",
    fullPage: false,
  });
});
