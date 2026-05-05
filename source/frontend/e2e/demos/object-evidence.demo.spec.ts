import { expect, test } from "@playwright/test";
import { copyFile, mkdir, stat } from "node:fs/promises";
import path from "node:path";
import { gotoApp, openMapContextMenu, resetRuntimeState, waitForBasemapReady, waitForLinkOpen, waitForNextPaint } from "../runtime";
import { API_BASE } from "../testUrls";
import { hideSubtitle, showSubtitle } from "../tutorialHelpers";

const PORT_CONTEXT_BBOX: [number, number, number, number] = [32.515, 29.9, 32.575, 29.955];
const PORT_AUDITED_CROP: [number, number, number, number] = [0.60, 0.05, 0.96, 0.43];

function cropToReviewBbox(
  contextBbox: [number, number, number, number],
  crop: [number, number, number, number],
): [number, number, number, number] {
  const [west, south, east, north] = contextBbox;
  const [xmin, ymin, xmax, ymax] = crop;
  return [
    west + (east - west) * xmin,
    north - (north - south) * ymax,
    west + (east - west) * xmax,
    north - (north - south) * ymin,
  ];
}

const PORT_REVIEW_BBOX = cropToReviewBbox(PORT_CONTEXT_BBOX, PORT_AUDITED_CROP);

test("records glowing CV object evidence boxes and tooltips", async ({ page, request }, testInfo) => {
  await resetRuntimeState(request);
  const mission = await request.post(`${API_BASE}/api/mission/start`, {
    data: {
      task_text:
        "Run Port Activity Object Evidence. Look for visible shipping container clusters, docked-vessel groups, and berth basin context.",
      bbox: PORT_REVIEW_BBOX,
      start_date: "2026-01-01",
      end_date: "2026-02-15",
      use_case_id: "maritime_activity",
      target_pack_id: "port",
      object_targets: [
        { label: "shipping container cluster", prompt: "Find shipping container clusters", class_key: "cargo", enabled: true },
        { label: "container yard cluster", prompt: "Find container yard clusters", class_key: "cargo", enabled: true },
        { label: "docked-vessel group", prompt: "Find docked-vessel groups along berth edges", class_key: "vessel", enabled: true },
        { label: "berth basin context", prompt: "Find berth basin context areas", class_key: "infrastructure", enabled: true },
      ],
    },
  });
  expect(mission.ok()).toBeTruthy();

  await page.route("**/api/vlm/grounding/batch", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        results: [
          {
            label: "shipping container cluster",
            bbox: [0.46, 0.28, 0.55, 0.39],
            bbox_format: "unit_xyxy",
            confidence: 0.82,
            color_key: "cargo",
            source_model: "visual_story_fixture",
            prompt: "Find shipping container clusters",
            runtime_truth_mode: "replay",
            imagery_origin: "esri_context",
            scoring_basis: "visual_only",
            count_quality: "activity_region",
          },
          {
            label: "container yard cluster",
            bbox: [0.50, 0.42, 0.60, 0.54],
            bbox_format: "unit_xyxy",
            confidence: 0.8,
            color_key: "cargo",
            source_model: "visual_story_fixture",
            prompt: "Find container yard clusters",
            runtime_truth_mode: "replay",
            imagery_origin: "esri_context",
            scoring_basis: "visual_only",
            count_quality: "activity_region",
          },
          {
            label: "docked-vessel group",
            bbox: [0.30, 0.64, 0.45, 0.75],
            bbox_format: "unit_xyxy",
            confidence: 0.77,
            color_key: "vessel",
            source_model: "visual_story_fixture",
            prompt: "Find docked-vessel groups along berth edges",
            runtime_truth_mode: "replay",
            imagery_origin: "esri_context",
            scoring_basis: "visual_only",
            count_quality: "activity_region",
          },
          {
            label: "berth basin context",
            bbox: [0.15, 0.62, 0.27, 0.74],
            bbox_format: "unit_xyxy",
            confidence: 0.72,
            color_key: "infrastructure",
            source_model: "visual_story_fixture",
            prompt: "Find berth basin context areas",
            runtime_truth_mode: "replay",
            imagery_origin: "esri_context",
            scoring_basis: "visual_only",
            count_quality: "activity_region",
          },
        ],
        summary: {
          target_pack_id: "port",
          total_boxes: 4,
          counts_by_label: {
            "shipping container cluster": 1,
            "container yard cluster": 1,
            "docked-vessel group": 1,
            "berth basin context": 1,
          },
          top_boxes: [],
          provenance: {
            runtime_truth_mode: "replay",
            imagery_origin: "esri_context",
            scoring_basis: "visual_only",
            model: "visual_story_fixture",
            exact_object_count: false,
            visual_audit_status: "approved",
          },
        },
        provenance: {
          runtime_truth_mode: "replay",
          imagery_origin: "cached_api",
          scoring_basis: "visual_only",
          model: "visual_story_fixture",
        },
        target_count: 4,
      }),
    });
  });

  await gotoApp(page);
  await waitForLinkOpen(page);
  await waitForBasemapReady(page);
  await showSubtitle(page, "Object Evidence Mode turns an operator prompt into compact CV boxes with provenance.", 1_700);

  await page.getByTestId("tab-mission").click();
  await expect(page.getByText("Run Port Activity Object Evidence")).toBeVisible({ timeout: 10_000 });
  await expect(page.getByTestId("bbox-badge")).toContainText("[32.55, 29.93, 32.57, 29.95]");
  await page.getByTestId("mission-panel-tab-targets").click();
  await expect(page.getByTestId("object-targets-panel")).toContainText("shipping container cluster", { timeout: 10_000 });
  await page.getByTestId("mission-panel-tab-plan").click();
  await page.getByTestId("open-evidence-tools").click();
  await expect(page.getByText("Visual Evidence Tools")).toBeVisible();
  await expect(page.getByTestId("map-scan-paused-hint")).toBeVisible();

  await showSubtitle(page, "Run the port target set inside the selected satellite mission bbox.", 1_300);
  await expect(page.getByTestId("vlm-mission-targets")).toContainText("shipping container cluster");
  await page.getByTestId("vlm-run-mission-targets").click();

  const result = page.getByTestId("vlm-grounding-result").filter({ hasText: "shipping container cluster" }).first();
  await expect(result).toBeVisible({ timeout: 10_000 });
  await expect(page.getByTestId("vlm-object-box-legend")).toContainText("shipping container cluster");
  await expect(page.getByTestId("vlm-object-box-legend")).not.toContainText("channel vessel");

  await showSubtitle(page, "The glowing squares are downlink candidates: label, bbox, confidence, model, mode, imagery, and basis stay attached.", 1_800);
  const canvasBox = await page.locator(".maplibregl-canvas").first().boundingBox();
  if (!canvasBox) {
    throw new Error("Map canvas did not expose a bounding box for CV tooltip capture.");
  }
  await page.mouse.move(canvasBox.x + canvasBox.width * 0.5, canvasBox.y + canvasBox.height * 0.45);
  await waitForNextPaint(page, 8);
  const mapTooltip = page.getByTestId("vlm-box-tooltip");
  let sawMapTooltip = false;
  for (const point of [
    { x: 0.505, y: 0.335 },
    { x: 0.375, y: 0.695 },
    { x: 0.210, y: 0.680 },
    { x: 0.550, y: 0.480 },
  ]) {
    await page.mouse.move(canvasBox.x + canvasBox.width * point.x, canvasBox.y + canvasBox.height * point.y, { steps: 12 });
    await waitForNextPaint(page, 2);
    if ((await mapTooltip.count()) > 0 && (await mapTooltip.first().isVisible())) {
      await expect(mapTooltip).toContainText(/shipping container cluster|container yard cluster|docked-vessel group|berth basin context/i, { timeout: 1_000 });
      sawMapTooltip = true;
      break;
    }
  }
  expect(sawMapTooltip).toBeTruthy();
  await expect(mapTooltip).toContainText("visual_story_fixture");
  await waitForNextPaint(page, 3);

  const currentMission = await request.get(`${API_BASE}/api/mission/current`);
  expect(currentMission.ok()).toBeTruthy();
  const currentPayload = await currentMission.json() as { mission?: { bbox?: number[] } };
  expect(currentPayload.mission?.bbox).toEqual(PORT_REVIEW_BBOX);

  const artifactDir = path.resolve("e2e", "artifacts", "object-evidence");
  const artifactScreenshot = path.join(artifactDir, "cv-object-evidence-local-audit.png");
  const artifactVideo = path.join(artifactDir, "video.webm");
  const docsScreenshotDir = path.resolve("..", "..", "docs", "media", "readme");
  const docsVideoDir = path.resolve("..", "..", "docs", "media", "videos");
  const docsScreenshot = path.join(docsScreenshotDir, "cv-object-evidence-local-audit.png");
  const docsVideo = path.join(docsVideoDir, "object-evidence-demo.webm");

  await mkdir(artifactDir, { recursive: true });
  await mkdir(docsScreenshotDir, { recursive: true });
  await mkdir(docsVideoDir, { recursive: true });
  await page.screenshot({ path: artifactScreenshot, fullPage: false });
  await copyFile(artifactScreenshot, docsScreenshot);
  await testInfo.attach("cv-object-evidence-local-audit", { path: artifactScreenshot, contentType: "image/png" });

  await hideSubtitle(page);
  await page.waitForTimeout(1_200);
  const video = page.video();
  if (!video) {
    throw new Error("Playwright video recording is unavailable for the Object Evidence demo.");
  }
  await page.close();
  await copyFile(await video.path(), artifactVideo);
  await copyFile(artifactVideo, docsVideo);

  const videoStat = await stat(artifactVideo);
  expect(videoStat.size).toBeGreaterThan(10_000);
  const docsVideoStat = await stat(docsVideo);
  expect(docsVideoStat.size).toBeGreaterThan(10_000);
  await testInfo.attach("cv-object-evidence-video", { path: artifactVideo, contentType: "video/webm" });
});
