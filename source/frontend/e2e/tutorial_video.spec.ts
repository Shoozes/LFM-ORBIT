import { test, expect, type Page } from "@playwright/test";
import { execFile } from "node:child_process";
import { copyFile, mkdir, readFile, stat } from "node:fs/promises";
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
const VOICEOVER_WORDS_PER_MINUTE = 135;
const VOICEOVER_PAD_MS = 1_200;
const VOICEOVER_MIN_MS = 4_600;

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

function voiceoverDurationMs(text: string, minMs = VOICEOVER_MIN_MS): number {
  const wordCount = text.trim().split(/\s+/).filter(Boolean).length;
  const readMs = Math.ceil((wordCount / VOICEOVER_WORDS_PER_MINUTE) * 60_000);
  return Math.max(minMs, readMs + VOICEOVER_PAD_MS);
}

async function showVoiceoverSubtitle(page: Page, text: string, minMs = VOICEOVER_MIN_MS) {
  await showSubtitle(page, text, voiceoverDurationMs(text, minMs));
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

async function commandExists(command: string): Promise<boolean> {
  try {
    await execFileAsync(command, ["-version"]);
    return true;
  } catch {
    return false;
  }
}

async function assertTutorialVideoQuality(videoPath: string) {
  const videoStats = await stat(videoPath);
  if (videoStats.size < 500_000) {
    throw new Error(`Tutorial video artifact is unexpectedly small: ${videoStats.size} bytes.`);
  }

  if (!(await commandExists("ffprobe")) || !(await commandExists("ffmpeg"))) {
    return;
  }

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
  if (!Number.isFinite(durationSeconds) || durationSeconds < 95 || durationSeconds > 190) {
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
  test.setTimeout(380_000);

  await mockTutorialVision(page);
  await resetRuntimeState(request);
  await loadSeededReplay(request, RONDONIA_REPLAY_ID);
  await gotoApp(page, "/?demo=1&demoCase=forest");
  await waitForLinkOpen(page);
  await waitForBasemapReady(page);
  await expect(page.getByText(`Replay Mission · ${RONDONIA_REPLAY_ID}`)).toBeVisible({ timeout: 15_000 });
  await waitForNextPaint(page, 8);

  await showVoiceoverSubtitle(
    page,
    "LFM-ORBIT opens on a ready Rondonia mission. The map and replay load without live credentials.",
  );
  await expect(page.locator("#tutorial-subtitle-container")).toBeVisible();

  await moveMouseToHighlight(page, "[data-testid='bbox-badge']");
  await showVoiceoverSubtitle(
    page,
    "The focus area is already mapped. The SELECT TOOL can redraw or confirm it.",
  );
  await removeHighlight(page);
  await page.getByTestId("bbox-badge").getByRole("button", { name: "Clear" }).click();

  await moveMouseToHighlight(page, "[data-testid='draw-area-button']");
  await showVoiceoverSubtitle(
    page,
    "The SELECT TOOL makes the review area explicit before agents spend compute or bandwidth.",
  );
  await page.getByTestId("draw-area-button").click();
  await removeHighlight(page);
  await drawMapBbox(page, { x: 0.34, y: 0.35 }, { x: 0.62, y: 0.61 });
  await page.getByTestId("tab-mission").click();
  await expect(page.getByTestId("bbox-badge")).toBeVisible({ timeout: 10_000 });

  await moveMouseToHighlight(page, "[data-testid='bbox-badge']");
  await showVoiceoverSubtitle(
    page,
    "The mission keeps one clear focus area. Target packs stay in the evidence packet, not as extra controls.",
  );
  await removeHighlight(page);

  await page.getByTestId("tab-agents").click();
  const chatInput = page.getByPlaceholder("Request replay, mission pack, link action...");
  await moveMouseToHighlight(page, "textarea[placeholder='Request replay, mission pack, link action...']");
  await showVoiceoverSubtitle(
    page,
    "GROUND AGENT handles operator workflow. It proposes changes before the app state moves.",
  );
  await chatInput.fill("load the Rondonia deforestation replay and explain the clearing, road, exposed soil, and boundary targets");
  await page.getByRole("button", { name: "Send" }).click();
  await removeHighlight(page);

  const proposal = page.getByTestId("ground-agent-proposal-card");
  await expect(proposal).toBeVisible({ timeout: 15_000 });
  await expect(proposal).toContainText("Rondonia Frontier Showcase Replay");
  await expect(proposal).toContainText("proxy_bands");
  await expect(proposal).toContainText("cached_api");
  await showVoiceoverSubtitle(
    page,
    "The action card shows truth mode, imagery source, scoring basis, reset impact, and refresh scope.",
  );

  await moveMouseToHighlight(page, "[data-testid='ground-agent-run-proposal']");
  await proposal.getByRole("button", { name: "Run Replay" }).click();
  await removeHighlight(page);
  await expect(proposal.getByRole("button", { name: "Confirmed" })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(`Loaded replay \`${RONDONIA_REPLAY_ID}\``)).toBeVisible({ timeout: 15_000 });
  await showVoiceoverSubtitle(
    page,
    "SATELLITE AGENT restores the completed scan: 9 cells swept, 4 retained, low-value cells pruned.",
  );

  await page.getByTestId("tab-mission").click();
  await openMapContextMenu(page, { xRatio: 0.48, yRatio: 0.48 });
  await page.getByText("Set Mission BBox Here").click();
  await expect(page.getByTestId("bbox-badge")).toBeVisible({ timeout: 10_000 });
  await moveMouseToHighlight(page, "[data-testid='bbox-badge']");
  await showVoiceoverSubtitle(
    page,
    "Changing the bbox updates the selected review area without opening extra tool panels.",
  );
  await removeHighlight(page);
  await showVoiceoverSubtitle(
    page,
    "The map remains the operational view. Scanned cells and retained alerts carry the evidence trail.",
  );

  await page.getByTestId("tab-logs").click();
  await expect(page.getByText(`Replay Bundle · ${RONDONIA_REPLAY_ID}`)).toBeVisible({ timeout: 10_000 });
  await expect(page.getByTestId("alert-button").filter({ hasText: RONDONIA_PRIMARY_CELL })).toBeVisible({ timeout: 10_000 });
  await showVoiceoverSubtitle(
    page,
    "Logs show pruning value: the ground side receives retained evidence packets, not every raw frame.",
  );
  await moveMouseToHighlight(page, "[data-testid='alert-button']");
  await page.getByTestId("alert-button").filter({ hasText: RONDONIA_PRIMARY_CELL }).click();
  await removeHighlight(page);

  await expect(page.getByText("Cached API Replay Evidence")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("inspect-object-evidence")).toContainText("deforestation", { timeout: 15_000 });
  await expect(page.getByText("Timelapse Evidence", { exact: true })).toBeVisible({ timeout: 15_000 });
  await waitForVideoReady(page, "video", 20_000);
  await showVoiceoverSubtitle(
    page,
    "TIMELAPSE shows change across acquisitions: canopy baseline, road-edge opening, then persistent clearing.",
  );

  await page.getByText("After Window").scrollIntoViewIfNeeded();
  await expect(page.getByText("2025-01-15").first()).toBeVisible({ timeout: 10_000 });
  await showVoiceoverSubtitle(
    page,
    "STATIC FRAME means one acquisition time. This retained frame is 2025-01-15.",
  );

  await page.getByText("Object Evidence").first().scrollIntoViewIfNeeded();
  await expect(page.getByTestId("inspect-object-evidence")).toContainText("clearing candidate");
  await showVoiceoverSubtitle(
    page,
    "Inspect keeps provenance together: capture time, bbox, scoring basis, proxy deltas, and CV regions.",
  );

  await moveMouseToHighlight(page, "[data-testid='analyze-button']");
  await page.locator("[data-testid='analyze-button']").click();
  await removeHighlight(page);
  await expect(page.getByText("offline_lfm_v1", { exact: true }).first()).toBeVisible({ timeout: 15_000 });
  await showVoiceoverSubtitle(
    page,
    "GROUND AGENT and the local model summarize the finding without overclaiming.",
  );

  await page.getByText("Model Training Export").scrollIntoViewIfNeeded();
  await expect(page.getByText("Export Assets")).toBeVisible({ timeout: 10_000 });
  await showVoiceoverSubtitle(
    page,
    "TAGGED TRAINING DATA keeps the task, bbox, date, source, scores, boxes, and review action.",
  );

  await moveMouseToHighlight(page, "[data-testid='proof-mode-button']");
  await showVoiceoverSubtitle(
    page,
    "COMPACT PROOF JSON is the downlink story: raw imagery stays local; the audit packet is small.",
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
  await showVoiceoverSubtitle(
    page,
    "The final proof shows retained evidence, confidence, provenance, CV BOXES, and compact JSON.",
  );

  await hideSubtitle(page);
  await showTutorialCard(
    page,
    {
      title: "Persistent land-use-change evidence retained for review.",
      body: "Rondonia replay evidence shows a clearing candidate with road-edge expansion and proxy-band support. Action: human review. Payload: compact proof JSON. Export: tagged training sample.",
      tags: [
        "deforestation_candidate",
        "clearing_region",
        "road_expansion",
        "temporal_change",
        "retained_evidence",
        "candidate_review",
      ],
    },
    8_500,
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
