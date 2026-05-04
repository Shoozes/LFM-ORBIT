import { test, expect, type Page } from "@playwright/test";
import { execFile } from "node:child_process";
import { copyFile, mkdir, readFile } from "node:fs/promises";
import path from "node:path";
import { promisify } from "node:util";
import {
  gotoApp,
  loadSeededReplay,
  openMapContextMenu,
  resetRuntimeState,
  waitForBasemapReady,
  waitForLinkOpen,
  waitForNextPaint,
  waitForVideoReady,
} from "./runtime";
import {
  drawMapBbox,
  hideSubtitle,
  moveMouseToHighlight,
  removeHighlight,
  showSubtitle,
  showTutorialCard,
} from "./tutorialHelpers";

test.use({
  video: "on",
  viewport: { width: 1440, height: 900 },
});

const execFileAsync = promisify(execFile);
const RONDONIA_REPLAY_ID = "rondonia_frontier_showcase";
const RONDONIA_PRIMARY_CELL = "sq_-10.0_-63.0";

const FOREST_BOXES = [
  {
    id: "tutorial_clearing_001",
    label: "clearing candidate",
    bbox: [0.24, 0.22, 0.64, 0.72],
    bbox_format: "unit_xyxy",
    confidence: 0.84,
    color_key: "land_cover_change",
    source_model: "tutorial_replay_fixture",
    prompt: "Find clearing candidate regions",
    runtime_truth_mode: "replay",
    imagery_origin: "cached_api",
    scoring_basis: "proxy_bands",
    count_quality: "region",
  },
  {
    id: "tutorial_road_001",
    label: "road expansion",
    bbox: [0.10, 0.48, 0.68, 0.58],
    bbox_format: "unit_xyxy",
    confidence: 0.73,
    color_key: "infrastructure",
    source_model: "tutorial_replay_fixture",
    prompt: "Find road expansion corridors",
    runtime_truth_mode: "replay",
    imagery_origin: "cached_api",
    scoring_basis: "proxy_bands",
    count_quality: "corridor",
  },
  {
    id: "tutorial_boundary_001",
    label: "canopy-loss boundary",
    bbox: [0.20, 0.18, 0.88, 0.84],
    bbox_format: "unit_xyxy",
    confidence: 0.76,
    color_key: "land_cover_change",
    source_model: "tutorial_replay_fixture",
    prompt: "Find canopy-loss boundaries",
    runtime_truth_mode: "replay",
    imagery_origin: "cached_api",
    scoring_basis: "proxy_bands",
    count_quality: "region",
  },
];

async function rondoniaTimelapseDataUrl(): Promise<string> {
  const videoPath = path.resolve("..", "backend", "assets", "seeded_data", "sh_07da3a0b.webm");
  return `data:video/webm;base64,${(await readFile(videoPath)).toString("base64")}`;
}

async function mockTutorialVision(page: Page) {
  const timelapseB64 = await rondoniaTimelapseDataUrl();
  const visionPayload = {
    results: FOREST_BOXES,
    provenance: {
      output_source: "tutorial_replay_fixture",
      model: "replay_fixture",
      runtime_truth_mode: "replay",
      imagery_origin: "cached_api",
      scoring_basis: "proxy_bands",
    },
    summary: {
      target_pack_id: "deforestation",
      total_boxes: FOREST_BOXES.length,
      counts_by_label: {
        "clearing candidate": 1,
        "road expansion": 1,
        "canopy-loss boundary": 1,
      },
      provenance: {
        output_source: "tutorial_replay_fixture",
        heuristic_fallback: false,
      },
    },
  };

  await page.route("**/api/vlm/grounding/batch", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(visionPayload),
    });
  });
  await page.route("**/api/vlm/grounding", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(visionPayload),
    });
  });
  await page.route("**/api/vlm/vqa", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        answer: "A persistent clearing candidate expands along a road-edge corridor, with exposed soil and a canopy-loss boundary visible in the retained cell.",
      }),
    });
  });
  await page.route("**/api/vlm/caption", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        caption: "Rondonia frontier land-use-change replay with clearing candidate regions, road expansion, and proxy-band evidence attached.",
      }),
    });
  });
  await page.route("**/api/timelapse/generate", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        video_b64: timelapseB64,
        frames_count: 5,
        format: "webm",
        source: "replay_cache",
        runtime_truth_mode: "replay",
        imagery_origin: "cached_api",
        scoring_basis: "proxy_bands",
        provenance: {
          kind: "replay_cache",
          label: "Cached API replay timelapse",
          cache_family: RONDONIA_REPLAY_ID,
        },
      }),
    });
  });
}

async function saveTrimmedTutorialVideo(rawVideoPath: string, docsVideoPath: string) {
  await mkdir(path.dirname(docsVideoPath), { recursive: true });
  try {
    await execFileAsync("ffmpeg", [
      "-y",
      "-ss",
      "4.0",
      "-i",
      rawVideoPath,
      "-an",
      "-c:v",
      "libvpx-vp9",
      "-b:v",
      "0",
      "-crf",
      "34",
      docsVideoPath,
    ]);
  } catch {
    await copyFile(rawVideoPath, docsVideoPath);
  }
}

async function assertTutorialVideoQuality(videoPath: string) {
  const durationResult = await execFileAsync("ffprobe", [
    "-v",
    "error",
    "-show_entries",
    "format=duration",
    "-of",
    "csv=p=0",
    videoPath,
  ]);
  const durationSeconds = Number(durationResult.stdout.trim());
  if (!Number.isFinite(durationSeconds) || durationSeconds < 58 || durationSeconds > 110) {
    throw new Error(`Tutorial video should be a paced walkthrough, got ${durationSeconds.toFixed(2)}s.`);
  }

  const frameHashResult = await execFileAsync("ffmpeg", [
    "-v",
    "error",
    "-i",
    videoPath,
    "-vf",
    "fps=1,scale=96:54,format=gray",
    "-f",
    "framemd5",
    "-",
  ]);
  const hashes = frameHashResult.stdout
    .split(/\r?\n/)
    .filter((line) => line && !line.startsWith("#"))
    .map((line) => line.split(",").at(-1)?.trim())
    .filter(Boolean);
  if (new Set(hashes).size < 18) {
    throw new Error("Tutorial video looks too static after sampling frames.");
  }
}

test("Tutorial: Rondonia end-to-end product walkthrough", async ({ page, request }, testInfo) => {
  test.setTimeout(260_000);

  await mockTutorialVision(page);
  await resetRuntimeState(request);
  await loadSeededReplay(request, RONDONIA_REPLAY_ID);
  await gotoApp(page, "/?demo=1&demoCase=forest");
  await waitForLinkOpen(page);
  await waitForBasemapReady(page);
  await expect(page.getByText(`Replay Mission · ${RONDONIA_REPLAY_ID}`)).toBeVisible({ timeout: 15_000 });
  await page.getByTestId("mission-panel-tab-targets").click();
  await expect(page.getByTestId("object-targets-panel")).toContainText("clearing candidate", { timeout: 15_000 });
  await page.getByTestId("mission-panel-tab-plan").click();
  await waitForNextPaint(page, 8);

  await showSubtitle(
    page,
    "LFM-ORBIT opens on a ready Rondonia mission. No loading screen, no blank map, and no live credentials needed.",
    3_100,
  );
  await expect(page.locator("#tutorial-subtitle-container")).toBeVisible();

  await moveMouseToHighlight(page, "[data-testid='bbox-badge']");
  await showSubtitle(
    page,
    "The active focus area is already mapped. The SELECT TOOL can redraw or confirm exactly what the mission studies.",
    3_200,
  );
  await removeHighlight(page);
  await page.getByTestId("bbox-badge").getByRole("button", { name: "Clear" }).click();

  await moveMouseToHighlight(page, "[data-testid='draw-area-button']");
  await showSubtitle(
    page,
    "The SELECT TOOL makes the operator's area explicit before any agent spends compute or bandwidth.",
    3_100,
  );
  await page.getByTestId("draw-area-button").click();
  await removeHighlight(page);
  await drawMapBbox(page, { x: 0.34, y: 0.35 }, { x: 0.62, y: 0.61 });
  await page.getByTestId("tab-mission").click();
  await expect(page.getByTestId("bbox-badge")).toBeVisible({ timeout: 10_000 });
  await page.getByTestId("mission-panel-tab-targets").click();
  await page.getByTestId("object-targets-panel").scrollIntoViewIfNeeded();

  await moveMouseToHighlight(page, "[data-testid='object-targets-panel']");
  await showSubtitle(
    page,
    "The mission target pack is concrete: clearing candidates, road expansion, exposed soil, forest edge, and canopy-loss boundaries.",
    3_500,
  );
  await removeHighlight(page);

  await page.getByTestId("tab-agents").click();
  const chatInput = page.getByPlaceholder("Request replay, mission pack, link action...");
  await moveMouseToHighlight(page, "textarea[placeholder='Request replay, mission pack, link action...']");
  await showSubtitle(
    page,
    "GROUND AGENT is the operator workflow layer. It proposes state changes instead of quietly mutating the app.",
    3_300,
  );
  await chatInput.fill("load the Rondonia deforestation replay and explain the clearing, road, exposed soil, and boundary targets");
  await page.getByRole("button", { name: "Send" }).click();
  await removeHighlight(page);

  const proposal = page.getByTestId("ground-agent-proposal-card");
  await expect(proposal).toBeVisible({ timeout: 15_000 });
  await expect(proposal).toContainText("Rondonia Frontier Showcase Replay");
  await expect(proposal).toContainText("proxy_bands");
  await expect(proposal).toContainText("cached_api");
  await showSubtitle(
    page,
    "The action card exposes truth mode, imagery origin, scoring basis, reset impact, and what will refresh.",
    4_200,
  );

  await moveMouseToHighlight(page, "[data-testid='ground-agent-run-proposal']");
  await proposal.getByRole("button", { name: "Run Replay" }).click();
  await removeHighlight(page);
  await expect(proposal.getByRole("button", { name: "Confirmed" })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(`Loaded replay \`${RONDONIA_REPLAY_ID}\``)).toBeVisible({ timeout: 15_000 });
  await showSubtitle(
    page,
    "SATELLITE AGENT restored a completed scan: 9 cells swept, 4 retained, and lower-value cells pruned before downlink.",
    4_300,
  );

  await page.getByTestId("tab-mission").click();
  await openMapContextMenu(page, { xRatio: 0.48, yRatio: 0.48 });
  await page.getByText("Set Mission BBox Here").click();
  await expect(page.getByTestId("vlm-run-mission-targets")).toBeVisible({ timeout: 10_000 });
  await moveMouseToHighlight(page, "[data-testid='vlm-run-mission-targets']");
  await showSubtitle(
    page,
    "CV BOXES run against the selected area and mission target pack. These are region-level review boxes, not legal claims.",
    3_700,
  );
  await page.getByTestId("vlm-run-mission-targets").click();
  await removeHighlight(page);
  await expect(page.getByTestId("vlm-grounding-result").first()).toContainText("clearing candidate", { timeout: 10_000 });
  await expect(page.getByTestId("vlm-object-box-legend")).toBeVisible({ timeout: 10_000 });
  await showSubtitle(
    page,
    "CV BOXES stay visible on the map with confidence and provenance so the retained evidence is reviewable.",
    3_800,
  );

  await expect(page.getByTestId("map-3d-toggle")).toBeVisible({ timeout: 10_000 });
  await moveMouseToHighlight(page, "[data-testid='map-3d-toggle']");
  await showSubtitle(
    page,
    "3D CONTEXT is optional. It helps terrain orientation, but it does not replace satellite evidence.",
    3_000,
  );
  await page.getByTestId("map-3d-toggle").click();
  await removeHighlight(page);
  await expect(page.getByTestId("map-3d-panel")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("This 3D view is terrain/context, not a satellite acquisition frame.")).toBeVisible({ timeout: 10_000 });
  await showSubtitle(
    page,
    "3D terrain is static context. Acquisition dates still come from the satellite replay and static frame metadata.",
    3_300,
  );
  await page.getByTestId("map-3d-close").click();

  await page.getByTestId("tab-logs").click();
  await expect(page.getByText(`Replay Bundle · ${RONDONIA_REPLAY_ID}`)).toBeVisible({ timeout: 10_000 });
  await expect(page.getByTestId("alert-button").filter({ hasText: RONDONIA_PRIMARY_CELL })).toBeVisible({ timeout: 10_000 });
  await showSubtitle(
    page,
    "Logs show why pruning matters: the ground side receives retained evidence packets, not every raw frame from every cell.",
    4_000,
  );
  await moveMouseToHighlight(page, "[data-testid='alert-button']");
  await page.getByTestId("alert-button").filter({ hasText: RONDONIA_PRIMARY_CELL }).click();
  await removeHighlight(page);

  await expect(page.getByText("Cached API Replay Evidence")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("inspect-object-evidence")).toContainText("deforestation", { timeout: 15_000 });
  await expect(page.getByText("Timelapse Evidence", { exact: true })).toBeVisible({ timeout: 15_000 });
  await waitForVideoReady(page, "video", 20_000);
  await showSubtitle(
    page,
    "TIMELAPSE mode shows temporal change across acquisition dates: baseline canopy, road-edge opening, then persistent clearing.",
    5_000,
  );

  await page.getByText("After Window").scrollIntoViewIfNeeded();
  await expect(page.getByText("2025-01-15").first()).toBeVisible({ timeout: 10_000 });
  await showSubtitle(
    page,
    "STATIC FRAME means one selected acquisition time. Here the current retained frame is 2025-01-15, not the 3D terrain context.",
    4_600,
  );

  await page.getByText("Object Evidence").first().scrollIntoViewIfNeeded();
  await expect(page.getByTestId("inspect-object-evidence")).toContainText("clearing candidate");
  await showSubtitle(
    page,
    "Inspect keeps confidence honest: source, capture time, bbox, scoring basis, proxy-band deltas, and CV region provenance stay together.",
    4_800,
  );

  await moveMouseToHighlight(page, "[data-testid='analyze-button']");
  await page.locator("[data-testid='analyze-button']").click();
  await removeHighlight(page);
  await expect(page.getByText("offline_lfm_v1", { exact: true }).first()).toBeVisible({ timeout: 15_000 });
  await showSubtitle(
    page,
    "GROUND AGENT review and the local evidence model summarize the finding without overclaiming beyond the imagery.",
    4_000,
  );

  await page.getByText("Model Training Export").scrollIntoViewIfNeeded();
  await expect(page.getByText("Export Assets")).toBeVisible({ timeout: 10_000 });
  await showSubtitle(
    page,
    "TAGGED TRAINING DATA keeps task text, bbox, capture date, imagery origin, scoring basis, CV boxes, confidence, and review action.",
    4_600,
  );

  await moveMouseToHighlight(page, "[data-testid='proof-mode-button']");
  await showSubtitle(
    page,
    "COMPACT PROOF JSON is the downlink story: keep raw imagery local, transmit a small auditable packet.",
    3_800,
  );
  await page.getByTestId("proof-mode-button").click();
  await removeHighlight(page);
  await expect(page.getByTestId("proof-mode-panel")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("demo-title")).toContainText("Rondonia land-use-change proof", { timeout: 30_000 });
  await expect(page.getByTestId("proof-cv-box").first()).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("proof-object-evidence")).toContainText("clearing candidate", { timeout: 30_000 });
  await expect(page.getByTestId("proof-confidence-stack")).toContainText("proxy band signal");
  await expect(page.getByTestId("proof-json")).toContainText("deforestation");
  await expect(page.getByTestId("proof-json")).toContainText("confidence_stack");
  await expect(page.getByTestId("proof-json")).toContainText("detections");
  await waitForNextPaint(page, 10);
  await showSubtitle(
    page,
    "The final proof shows retained evidence, confidence components, provenance, CV BOXES, and a compact JSON payload.",
    5_500,
  );

  await hideSubtitle(page);
  await showTutorialCard(
    page,
    {
      title: "Persistent land-use-change evidence retained for review.",
      body: "Rondonia replay evidence shows a clearing candidate region with road-edge expansion and proxy-band support. Action: defer for human review. Payload: compact proof JSON. Export: tagged training sample.",
      tags: [
        "deforestation_candidate",
        "clearing_region",
        "road_expansion",
        "temporal_change",
        "retained_evidence",
        "candidate_review",
      ],
    },
    6_000,
  );
  await expect(page.getByTestId("tutorial-final-card")).toBeVisible();

  const video = page.video();
  if (!video) {
    throw new Error("Tutorial video recording is unavailable.");
  }
  const docsVideoPath = path.resolve("..", "..", "docs", "media", "videos", "tutorial_video.webm");
  await page.close();
  await saveTrimmedTutorialVideo(await video.path(), docsVideoPath);
  await assertTutorialVideoQuality(docsVideoPath);
  await testInfo.attach("docs-tutorial-video", { path: docsVideoPath, contentType: "video/webm" });
});
