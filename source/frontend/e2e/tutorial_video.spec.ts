import { test, expect } from "@playwright/test";
import { gotoApp, resetRuntimeState, waitForLinkOpen } from "./runtime";
import {
  drawMapBbox,
  getMapCanvasBox,
  hideSubtitle,
  moveMouseToHighlight,
  removeHighlight,
  showSubtitle,
} from "./tutorialHelpers";

test.use({ 
  video: "on", 
  viewport: { width: 1440, height: 900 }
});

test("Tutorial: How LFM Orbit AI Detects Deforestation", async ({ page, request }) => {
  test.setTimeout(75_000);

  await resetRuntimeState(request);
  await gotoApp(page);
  await waitForLinkOpen(page);
  await showSubtitle(page, "Welcome to LFM Orbit. This walkthrough shows the deforestation triage loop.", 1800);
  await showSubtitle(page, "The app connects map context, anomaly scoring, and local ground validation.", 1800);

  await showSubtitle(page, "First, the operator defines the area of interest and task.", 1600);
  await moveMouseToHighlight(page, "[data-testid='tab-mission']");
  await page.locator("[data-testid='tab-mission']").click();
  await removeHighlight(page);

  await moveMouseToHighlight(page, "button:has-text('Draw Area on Map')");
  await page.getByText("Draw Area on Map").click();
  await removeHighlight(page);
  await expect(page.getByText("DRAWING MODE ACTIVE")).toBeVisible();
  await page.waitForTimeout(250);

  await showSubtitle(page, "A bounding box marks the exact scene to monitor.", 1600);
  await drawMapBbox(page, { x: 0.16, y: 0.2 }, { x: 0.42, y: 0.56 });

  await showSubtitle(page, "Next, the operator issues a natural-language mission.", 1600);
  await page.fill('textarea', "Scan this region for recent clear-cut deforestation.");

  const replayButtonSelector = "[data-testid='load-replay-rondonia_frontier_judge']";
  const replayButton = page.locator(replayButtonSelector);
  await moveMouseToHighlight(page, replayButtonSelector);
  await expect(replayButton).toBeEnabled();
  await replayButton.click();
  await removeHighlight(page);
  await expect(page.getByText("REPLAY ACTIVE: rondonia_frontier_judge")).toBeVisible({ timeout: 15_000 });
  await showSubtitle(page, "For a deterministic walkthrough, Orbit restores a completed seeded mission.", 1800);
  await page.reload();
  await waitForLinkOpen(page);

  await showSubtitle(page, "The dialogue bus shows the handoff between ground and orbital agents.", 1800);
  await page.locator("[data-testid='tab-agents']").click();
  await expect(page.getByTestId("header-agent-bus")).toBeVisible();

  await showSubtitle(page, "As the sweep progresses, only high-signal anomalies are retained.", 1800);
  await page.locator("[data-testid='tab-logs']").click();
  await showSubtitle(page, "Those flagged cells appear in the alerts log for review.", 1800);
  await page.waitForSelector("[data-testid='alert-button']", { timeout: 45_000 });
  const firstAlert = page.locator("[data-testid='alert-button']").first();
  await expect(firstAlert).toBeVisible({ timeout: 5000 });
  await firstAlert.click();
  await showSubtitle(page, "The evidence panel exposes temporal windows, signal deltas, and imagery context.", 1800);
  await moveMouseToHighlight(page, "button:has-text('Analyze')");
  await page.locator("[data-testid='analyze-button']").click();
  await removeHighlight(page);
  await expect(page.getByText("offline_lfm_v1", { exact: true }).first()).toBeVisible({ timeout: 15_000 });
  await showSubtitle(page, "Ground analysis can confirm whether the signal matches canopy loss.", 1800);

  await showSubtitle(page, "The same area can be opened as an orbital timelapse for historical context.", 1800);
  const replayBox = await getMapCanvasBox(page);
  await page.mouse.move(replayBox.x + replayBox.width * 0.36, replayBox.y + replayBox.height * 0.32);
  await page.mouse.click(replayBox.x + replayBox.width * 0.36, replayBox.y + replayBox.height * 0.32, { button: "right" });
  await page.getByText("▷ Generate Temporal Timelapse").click();
  await expect(page.getByText("Orbital Timelapse", { exact: true })).toBeVisible({ timeout: 15_000 });
  await showSubtitle(page, "That closes the loop from scan, to alert, to validated visual evidence.", 1800);
  await hideSubtitle(page);
});
