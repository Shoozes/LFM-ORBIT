import { test, expect } from "@playwright/test";
import { copyFile, mkdir } from "node:fs/promises";
import path from "node:path";
import { gotoApp, resetRuntimeState, waitForLinkOpen } from "./runtime";
import {
  hideSubtitle,
  moveMouseToHighlight,
  removeHighlight,
  showSubtitle,
} from "./tutorialHelpers";

test.use({ 
  video: "on", 
  viewport: { width: 1440, height: 900 }
});

test("Tutorial: mission replay workflow across maritime and mining evidence", async ({ page, request }, testInfo) => {
  test.setTimeout(120_000);

  await resetRuntimeState(request);
  await gotoApp(page, "/?demo=1");
  await waitForLinkOpen(page);
  await showSubtitle(page, "LFM Orbit opens in mission control. The operator starts from cached real satellite replays.", 1800);
  await showSubtitle(page, "This walkthrough uses different mission areas so the video does not look like one static location.", 1800);

  await showSubtitle(page, "First, open the mission catalog and load the Singapore Strait maritime replay.", 1700);
  await moveMouseToHighlight(page, "[data-testid='tab-mission']");
  await page.locator("[data-testid='tab-mission']").click();
  await removeHighlight(page);

  const maritimeReplaySelector = "[data-testid='load-replay-singapore_maritime_replay']";
  await moveMouseToHighlight(page, maritimeReplaySelector);
  await expect(page.locator(maritimeReplaySelector)).toBeVisible({ timeout: 15_000 });
  await page.locator(maritimeReplaySelector).click();
  await removeHighlight(page);
  await expect(page.getByText("REPLAY ACTIVE: singapore_maritime_replay")).toBeVisible({ timeout: 15_000 });
  await showSubtitle(page, "The replay restores a completed orbital run with cloud-gated Sentinel frames.", 1900);

  await page.locator("[data-testid='tab-logs']").click();
  await expect(page.getByTestId("alert-button").filter({ hasText: "maritime_singapore_strait" })).toBeVisible({ timeout: 15_000 });
  await showSubtitle(page, "The alert log names the retained cell and keeps the cloudy rejected windows in the evidence trail.", 1900);

  await page.getByTestId("alert-button").filter({ hasText: "maritime_singapore_strait" }).click();
  await expect(page.getByText("Cached API Replay Evidence", { exact: true })).toBeVisible({ timeout: 15_000 });
  await showSubtitle(page, "Inspect shows the evidence frame, reason codes, and replay provenance for review.", 1900);

  await moveMouseToHighlight(page, "[data-testid='analyze-button']");
  await page.locator("[data-testid='analyze-button']").click();
  await removeHighlight(page);
  await expect(page.getByText("offline_lfm_v1", { exact: true }).first()).toBeVisible({ timeout: 15_000 });
  await showSubtitle(page, "Ground validation turns the selected replay cell into a compact model-backed finding.", 1900);

  await showSubtitle(page, "Now switch missions. The operator replaces the maritime replay with a clean Atacama mining replay.", 1900);
  await page.locator("[data-testid='tab-mission']").click();
  const miningReplaySelector = "[data-testid='load-replay-atacama_mining_replay']";
  await moveMouseToHighlight(page, miningReplaySelector);
  await expect(page.locator(miningReplaySelector)).toBeVisible({ timeout: 15_000 });
  await page.locator(miningReplaySelector).click();
  await removeHighlight(page);
  await expect(page.getByText("REPLAY ACTIVE: atacama_mining_replay")).toBeVisible({ timeout: 15_000 });
  await showSubtitle(page, "The mining replay keeps source, bbox, prompt, and capture windows attached to a clearer arid scene.", 2000);

  await page.locator("[data-testid='tab-logs']").click();
  await expect(page.getByTestId("alert-button").filter({ hasText: "mining_atacama_open_pit" })).toBeVisible({ timeout: 15_000 });
  await page.getByTestId("alert-button").filter({ hasText: "mining_atacama_open_pit" }).click();
  await expect(page.getByText("Cached API Replay Evidence", { exact: true })).toBeVisible({ timeout: 15_000 });
  await showSubtitle(page, "Different mission, different geography, different evidence category. Same operator flow.", 1900);

  await showSubtitle(page, "Open Proof Mode to export the proof screen with payload, latency, model, and provenance fields.", 1900);
  await moveMouseToHighlight(page, "[data-testid='proof-mode-button']");
  await page.getByTestId("proof-mode-button").click();
  await removeHighlight(page);
  await expect(page.getByTestId("proof-mode-panel")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("proof-json")).toBeVisible({ timeout: 30_000 });
  await showSubtitle(page, "The final frame is useful muted: image, bbox, evidence, model output, and JSON proof are all on screen.", 2200);
  await hideSubtitle(page);

  const video = page.video();
  if (!video) {
    throw new Error("Tutorial video recording is unavailable.");
  }
  const docsVideoPath = path.resolve("..", "..", "docs", "tutorial_video.webm");
  await mkdir(path.dirname(docsVideoPath), { recursive: true });
  await page.close();
  await copyFile(await video.path(), docsVideoPath);
  await testInfo.attach("docs-tutorial-video", { path: docsVideoPath, contentType: "video/webm" });
});
