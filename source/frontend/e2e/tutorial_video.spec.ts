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
  if (!Number.isFinite(durationSeconds) || durationSeconds < 115 || durationSeconds > 240) {
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
  test.setTimeout(380_000);

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
    "LFM-ORBIT scans areas on a map, checks image FRAMES over time, and looks for the ANOMALY you ask for.",
    5_800,
  );
  await expect(page.locator("#tutorial-subtitle-container")).toBeVisible();

  await showVoiceoverSubtitle(
    page,
    "One AI is the SPACE AGENT. It prunes low-value tiles before downlink. One AI is the GROUND AGENT. It turns the evidence into something a person can review.",
    7_400,
  );

  await moveMouseToHighlight(page, "[data-testid='map-area-tools']");
  await showVoiceoverSubtitle(
    page,
    "Area Tools now stay on the map. This is where you see the selected bbox, cell count, Draw, and Clear.",
    5_200,
  );
  await removeHighlight(page);

  await page.getByTestId("tab-agents").click();
  const chatInput = page.getByPlaceholder("Request replay, mission pack, link action...");
  await moveMouseToHighlight(page, "textarea[placeholder='Request replay, mission pack, link action...']");
  await showVoiceoverSubtitle(
    page,
    "You can launch a mission with plain chat. No dashboard hunting: just ask for the search.",
  );
  await chatInput.fill("run a Rondonia deforestation mission");
  await page.getByRole("button", { name: "Send" }).click();
  await removeHighlight(page);

  const missionProposal = page.getByTestId("ground-agent-proposal-card").last();
  await expect(missionProposal).toBeVisible({ timeout: 15_000 });
  await expect(missionProposal).toContainText("Amazon frontier deforestation");
  await expect(missionProposal).toContainText("deforestation");
  await showVoiceoverSubtitle(
    page,
    "The GROUND AGENT turns the request into a bbox, date range, target pack, and safety limits before anything changes.",
  );

  await moveMouseToHighlight(page, "[data-testid='ground-agent-run-proposal']");
  await missionProposal.getByRole("button", { name: "Launch Mission" }).click();
  await removeHighlight(page);
  await expect(page.locator('[data-testid="mission-progress-status"], [data-testid="mission-complete-summary"]').first()).toBeVisible({ timeout: 30_000 });
  await showVoiceoverSubtitle(
    page,
    "Mission launched. The SPACE AGENT starts sweeping the selected GRID cell by cell.",
  );

  await page.getByTestId("tab-mission").click();
  await expect(page.locator('[data-testid="mission-progress-status"], [data-testid="mission-complete-summary"]').first()).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/cells scanned|cells recorded/i).first()).toBeVisible({ timeout: 30_000 });
  await moveMouseToHighlight(page, "[data-testid='map-area-tools']");
  await showVoiceoverSubtitle(
    page,
    "Each square is a map tile. Area Tools shows the active selection while the scan reads cells and compares FRAMES inside the time window.",
    5_800,
  );
  await removeHighlight(page);
  await showVoiceoverSubtitle(
    page,
    "Most cells are noise. Possible ANOMALY packets get retained so the ground side can focus on evidence instead of hundreds of raw images.",
    6_200,
  );

  await page.getByTestId("tab-agents").click();
  await moveMouseToHighlight(page, "textarea[placeholder='Request replay, mission pack, link action...']");
  await showVoiceoverSubtitle(
    page,
    "For a show-ready walkthrough, we ask the GROUND AGENT to load the same Rondonia story as a deterministic replay.",
  );
  await chatInput.fill("load the Rondonia deforestation replay and explain the clearing, road, exposed soil, and boundary targets");
  await page.getByRole("button", { name: "Send" }).click();
  await removeHighlight(page);

  const replayProposal = page.getByTestId("ground-agent-proposal-card").last();
  await expect(replayProposal).toBeVisible({ timeout: 15_000 });
  await expect(replayProposal).toContainText("Rondonia Frontier Showcase Replay");
  await expect(replayProposal).toContainText("proxy_bands");
  await expect(replayProposal).toContainText("cached_api");
  await showVoiceoverSubtitle(
    page,
    "The action card shows truth mode, imagery source, scoring basis, reset impact, and refresh scope.",
  );

  await moveMouseToHighlight(page, "[data-testid='ground-agent-run-proposal']");
  await replayProposal.getByRole("button", { name: "Run Replay" }).click();
  await removeHighlight(page);
  await expect(page.getByText(`REPLAY ACTIVE: ${RONDONIA_REPLAY_ID}`)).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("tab-inspect")).toHaveClass(/border-zinc-900/);
  await showVoiceoverSubtitle(
    page,
    "The replay restores a completed scan: cells swept, low-value areas pruned, and retained evidence ready for review.",
  );

  await page.getByTestId("tab-logs").click();
  await expect(page.getByText(`Replay Bundle · ${RONDONIA_REPLAY_ID}`)).toBeVisible({ timeout: 10_000 });
  await expect(page.getByTestId("alert-button").filter({ hasText: RONDONIA_PRIMARY_CELL })).toBeVisible({ timeout: 10_000 });
  await showVoiceoverSubtitle(
    page,
    "Logs show the point of AI in space: the ground side receives retained evidence packets, not every raw frame.",
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
    "TIMELAPSE shows acquisition FRAMES over time: canopy baseline, road-edge opening, then persistent clearing.",
  );

  await page.getByText("After Window").scrollIntoViewIfNeeded();
  await expect(page.getByText("2025-01-15").first()).toBeVisible({ timeout: 10_000 });
  await showVoiceoverSubtitle(
    page,
    "A STATIC FRAME is one date. A timelapse is the sequence that makes change visible.",
  );

  await page.getByText("Object Evidence").first().scrollIntoViewIfNeeded();
  await expect(page.getByTestId("inspect-object-evidence")).toContainText("clearing candidate");
  await showVoiceoverSubtitle(
    page,
    "CV BOXES turn pixels into SEMANTIC DATA: clearing candidate, road expansion, canopy-loss boundary.",
  );

  await moveMouseToHighlight(page, "[data-testid='analyze-button']");
  await page.locator("[data-testid='analyze-button']").click();
  await removeHighlight(page);
  await expect(page.getByText(/offline_lfm_v1|LFM2\.5-VL-450M-Q4_0\.gguf/).first()).toBeVisible({ timeout: 15_000 });
  await showVoiceoverSubtitle(
    page,
    "The local model summarizes the finding without overclaiming. This matters for HIGH-STAKES review.",
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
    "COMPACT PROOF JSON is the downlink story: raw imagery can stay local while the audit packet stays small.",
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
    "The final PROOF shows retained evidence, confidence, provenance, CV BOXES, and compact JSON.",
  );

  await hideSubtitle(page);
  await showTutorialCard(
    page,
    {
      title: "AI-in-space triage, AI-on-ground proof.",
      body: "Plain request -> mission -> grid scan -> retained evidence -> proof JSON. Rondonia replay evidence shows clearing candidates, road-edge expansion, and proxy-band support with provenance attached.",
      tags: [
        "ai_in_space",
        "ground_agent",
        "grid_scan",
        "semantic_data",
        "proof_json",
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
