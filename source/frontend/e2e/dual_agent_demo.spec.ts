import { test, expect } from "@playwright/test";
import { gotoApp, resetRuntimeState, waitForLinkOpen } from "./runtime";
import {
  drawMapBbox,
  hideSubtitle,
  moveMouseToHighlight,
  removeHighlight,
  showSubtitle,
} from "./tutorialHelpers";

test.use({ 
  video: "on", 
  viewport: { width: 1440, height: 900 }
});

test("Tutorial: Dual-Agent Architecture Demo", async ({ page, request }) => {
  test.setTimeout(75_000);

  await resetRuntimeState(request);
  await gotoApp(page);
  await waitForLinkOpen(page);
  await showSubtitle(page, "LFM Orbit utilizes a dual-agent architecture.", 1800);
  await showSubtitle(page, "A satellite agent triages imagery before sending compact findings to Earth.", 1800);

  await page.locator("[data-testid='tab-mission']").click();
  await page.getByText("Draw Area on Map").click();

  await showSubtitle(page, "The operator defines a focus area and mission objective.", 1800);
  await expect(page.getByText("DRAWING MODE ACTIVE")).toBeVisible();
  await drawMapBbox(page, { x: 0.15, y: 0.2 }, { x: 0.42, y: 0.52 });

  await page.fill('textarea', "Scan this region for recent clear-cut deforestation.");
  const replayButtonSelector = "[data-testid='load-replay-rondonia_frontier_showcase']";
  const replayButton = page.locator(replayButtonSelector);
  await moveMouseToHighlight(page, replayButtonSelector);
  await expect(replayButton).toBeEnabled();
  await replayButton.click();
  await removeHighlight(page);
  await expect(page.getByText("REPLAY ACTIVE: rondonia_frontier_showcase")).toBeVisible({ timeout: 15_000 });
  await showSubtitle(page, "Replay restores the SAT/GND exchange without waiting on realtime scan timing.", 1800);

  await page.locator("[data-testid='tab-agents']").click();
  await expect(page.getByTestId("header-agent-bus")).toBeVisible();
  await expect(page.getByText("Historical replay trace loaded")).toBeVisible({ timeout: 15_000 });
  await showSubtitle(page, "Ground and satellite messages converge on the dialogue bus.", 1800);
  await expect(page.getByText(/satellite|ground/i).first()).toBeVisible({ timeout: 20_000 });
  await showSubtitle(page, "Only actionable anomalies are escalated for ground validation.", 1800);
  await moveMouseToHighlight(page, "[data-testid='header-agent-bus']");
  await page.waitForTimeout(1500);
  await removeHighlight(page);
  await hideSubtitle(page);
});
