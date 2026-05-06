import { test, expect, type Page } from "@playwright/test";
import { execFile } from "node:child_process";
import { copyFile, mkdir, readFile, stat } from "node:fs/promises";
import path from "node:path";
import { promisify } from "node:util";
import {
  gotoApp,
  resetRuntimeState,
  waitForBasemapReady,
  waitForLinkOpen,
  waitForNextPaint,
  waitForVideoReady,
} from "./runtime";
import {
  clickWithPulse,
  hideSubtitle,
  moveMouseToHighlight,
  removeHighlight,
  showSubtitle,
  showTutorialCard,
  typeLikeOperator,
} from "./tutorialHelpers";

test.use({
  video: "on",
  viewport: { width: 1440, height: 900 },
});

const execFileAsync = promisify(execFile);
const RONDONIA_REPLAY_ID = "rondonia_frontier_showcase";
const RONDONIA_PRIMARY_CELL = "sq_-10.0_-63.0";
const VOICEOVER_WORDS_PER_MINUTE = 122;
const VOICEOVER_PAD_MS = 1_900;
const VOICEOVER_MIN_MS = 5_600;

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
  if (!Number.isFinite(durationSeconds) || durationSeconds < 150 || durationSeconds > 300) {
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

test("Tutorial: chat-launched map scan to proof walkthrough", async ({ page, request }, testInfo) => {
  test.setTimeout(460_000);

  await mockTutorialVision(page);
  await resetRuntimeState(request);
  await gotoApp(page, "/?demo=1&demoCase=forest");
  await waitForLinkOpen(page);
  await waitForBasemapReady(page);
  await expect(page.getByText("New Mission", { exact: true })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("Ready: selected area will be scanned.")).toBeVisible({ timeout: 15_000 });
  await waitForNextPaint(page, 8);

  await showVoiceoverSubtitle(
    page,
    "LFM-ORBIT scans an area on a map, checks the image FRAMES inside a time window, and looks for the ANOMALY you ask for.",
    7_200,
  );
  await expect(page.locator("#tutorial-subtitle-container")).toBeVisible();

  await showVoiceoverSubtitle(
    page,
    "There are two agents. The SPACE AGENT sweeps the grid and prunes low-value imagery. The GROUND AGENT turns the retained evidence into something a person can review.",
    8_600,
  );

  await moveMouseToHighlight(page, "[data-testid='map-area-tools']");
  await showVoiceoverSubtitle(
    page,
    "The selected area stays visible on the map: bbox, cell count, Draw, and Clear are always close to the imagery.",
    6_400,
  );
  await removeHighlight(page);

  await clickWithPulse(page, page.getByTestId("tab-agents"), "OPEN");
  const chatInput = page.getByPlaceholder("Request replay, mission pack, link action...");
  await moveMouseToHighlight(page, "textarea[placeholder='Request replay, mission pack, link action...']");
  await showVoiceoverSubtitle(
    page,
    "You can launch a mission with plain chat. Just ask the GROUND AGENT for the search you want.",
  );
  await typeLikeOperator(page, chatInput, "run a Rondonia deforestation mission", { label: "TYPE" });
  await clickWithPulse(page, page.getByRole("button", { name: "Send" }), "SEND");
  await removeHighlight(page);

  const missionProposal = page.getByTestId("ground-agent-proposal-card").last();
  await expect(missionProposal).toBeVisible({ timeout: 15_000 });
  await expect(missionProposal).toContainText("Amazon frontier deforestation");
  await expect(missionProposal).toContainText("deforestation");
  await showVoiceoverSubtitle(
    page,
    "Before it changes the app, the GROUND AGENT proposes the bbox, date range, search target, and safety limits.",
  );

  await moveMouseToHighlight(page, "[data-testid='ground-agent-run-proposal']");
  await clickWithPulse(page, missionProposal.getByRole("button", { name: "Launch Mission" }), "LAUNCH");
  await removeHighlight(page);
  await expect(page.locator('[data-testid="mission-progress-status"], [data-testid="mission-complete-summary"]').first()).toBeVisible({ timeout: 30_000 });
  await showVoiceoverSubtitle(
    page,
    "Mission launched. The SPACE AGENT starts sweeping the selected GRID, cell by cell.",
  );

  await clickWithPulse(page, page.getByTestId("tab-mission"), "OPEN");
  await expect(page.locator('[data-testid="mission-progress-status"], [data-testid="mission-complete-summary"]').first()).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/cells scanned|cells recorded/i).first()).toBeVisible({ timeout: 30_000 });
  await moveMouseToHighlight(page, "[data-testid='map-area-tools']");
  await showVoiceoverSubtitle(
    page,
    "Each square is a map tile. Inside each tile, the app compares ACQUISITION FRAMES from the mission time window.",
    7_000,
  );
  await removeHighlight(page);
  await showVoiceoverSubtitle(
    page,
    "Most cells are noise. The important part is fast triage through hundreds or thousands of images without making a person inspect every frame.",
    8_200,
  );

  await clickWithPulse(page, page.getByTestId("tab-agents"), "OPEN");
  await moveMouseToHighlight(page, "textarea[placeholder='Request replay, mission pack, link action...']");
  await showVoiceoverSubtitle(
    page,
    "For a clean demo, we ask the GROUND AGENT to load a deterministic Rondonia replay. That keeps the proof repeatable.",
  );
  await typeLikeOperator(
    page,
    chatInput,
    "load the Rondonia deforestation replay and explain the clearing, road, exposed soil, and boundary targets",
    { label: "TYPE", delayMs: 32 },
  );
  await clickWithPulse(page, page.getByRole("button", { name: "Send" }), "SEND");
  await removeHighlight(page);

  const replayProposal = page.getByTestId("ground-agent-proposal-card").last();
  await expect(replayProposal).toBeVisible({ timeout: 15_000 });
  await expect(replayProposal).toContainText("Rondonia Frontier Showcase Replay");
  await expect(replayProposal).toContainText("proxy_bands");
  await expect(replayProposal).toContainText("cached_api");
  await showVoiceoverSubtitle(
    page,
    "The action card shows what will happen: truth mode, imagery source, scoring basis, and what state will be refreshed.",
  );

  await moveMouseToHighlight(page, "[data-testid='ground-agent-run-proposal']");
  await clickWithPulse(page, replayProposal.getByRole("button", { name: "Run Replay" }), "RUN");
  await removeHighlight(page);
  await expect(page.getByText(`REPLAY ACTIVE: ${RONDONIA_REPLAY_ID}`)).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("tab-inspect")).toHaveClass(/border-zinc-900/);
  await showVoiceoverSubtitle(
    page,
    "The replay restores a completed scan: grid cells swept, low-value imagery pruned, and retained evidence ready for review.",
  );

  await clickWithPulse(page, page.getByTestId("tab-logs"), "OPEN");
  await expect(page.getByText(`Replay Bundle · ${RONDONIA_REPLAY_ID}`)).toBeVisible({ timeout: 10_000 });
  await expect(page.getByTestId("alert-button").filter({ hasText: RONDONIA_PRIMARY_CELL })).toBeVisible({ timeout: 10_000 });
  await showVoiceoverSubtitle(
    page,
    "Logs show the point of AI in space: the ground side receives retained evidence packets, not every raw image.",
  );
  await moveMouseToHighlight(page, "[data-testid='alert-button']");
  await clickWithPulse(page, page.getByTestId("alert-button").filter({ hasText: RONDONIA_PRIMARY_CELL }), "INSPECT");
  await removeHighlight(page);

  await expect(page.getByText("Cached API Replay Evidence")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("inspect-object-evidence")).toContainText("deforestation", { timeout: 15_000 });
  await expect(page.getByText("Timelapse Evidence", { exact: true })).toBeVisible({ timeout: 15_000 });
  await waitForVideoReady(page, "video", 20_000);
  await moveMouseToHighlight(page, "video");
  await showVoiceoverSubtitle(
    page,
    "This is the visual part: a TIMELAPSE of ACQUISITION FRAMES. Baseline canopy, road-edge opening, then persistent clearing.",
    8_800,
  );
  await removeHighlight(page);

  await page.getByText("After Window").scrollIntoViewIfNeeded();
  await expect(page.getByText("2025-01-15").first()).toBeVisible({ timeout: 10_000 });
  await showVoiceoverSubtitle(
    page,
    "A STATIC FRAME is one date. The sequence is what makes change visible and reviewable.",
  );

  await page.getByText("Object Evidence").first().scrollIntoViewIfNeeded();
  await expect(page.getByTestId("inspect-object-evidence")).toContainText("clearing candidate");
  await moveMouseToHighlight(page, "[data-testid='inspect-object-evidence']");
  await showVoiceoverSubtitle(
    page,
    "CV BOXES turn pixels into SEMANTIC DATA: clearing candidate, road expansion, canopy-loss boundary.",
  );
  await removeHighlight(page);

  await moveMouseToHighlight(page, "[data-testid='analyze-button']");
  await clickWithPulse(page, "[data-testid='analyze-button']", "ANALYZE");
  await removeHighlight(page);
  await expect(page.getByText(/offline_lfm_v1|LFM2\.5-VL-450M-Q4_0\.gguf/).first()).toBeVisible({ timeout: 15_000 });
  await showVoiceoverSubtitle(
    page,
    "The local model summarizes the evidence without overclaiming. That matters when the review may be HIGH-STAKES.",
  );

  await page.getByText("Model Training Export").scrollIntoViewIfNeeded();
  await expect(page.getByText("Export Assets")).toBeVisible({ timeout: 10_000 });
  await showVoiceoverSubtitle(
    page,
    "The same packet can become TAGGED TRAINING DATA: task, bbox, date, source, scores, boxes, and review action.",
  );

  await moveMouseToHighlight(page, "[data-testid='proof-mode-button']");
  await showVoiceoverSubtitle(
    page,
    "COMPACT PROOF JSON is the downlink story: raw imagery can stay local while the audit packet stays small.",
  );
  await clickWithPulse(page, page.getByTestId("proof-mode-button"), "PROOF");
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
  await moveMouseToHighlight(page, "[data-testid='proof-cv-box']");
  await showVoiceoverSubtitle(
    page,
    "FOUND: retained evidence for clearing candidates, road-edge expansion, and a canopy-loss boundary.",
    7_200,
  );
  await removeHighlight(page);
  await moveMouseToHighlight(page, "[data-testid='proof-json']");
  await showVoiceoverSubtitle(
    page,
    "The final PROOF ties it together: where it was found, why it was retained, confidence, provenance, CV BOXES, and compact JSON.",
    8_800,
  );
  await removeHighlight(page);

  await hideSubtitle(page);
  await showTutorialCard(
    page,
    {
      title: "Result: anomaly found, evidence retained, proof ready.",
      body: "LFM-ORBIT turns a plain request into a map scan, lets the space agent prune the imagery, lets the ground agent review the retained evidence, and ends with proof JSON a human can audit.",
      tags: [
        "ai_in_space",
        "ground_agent",
        "grid_scan",
        "anomaly_found",
        "semantic_data",
        "proof_json",
      ],
    },
    13_000,
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
