import { expect, type APIRequestContext, type Page, type TestInfo } from "@playwright/test";
import { execFile } from "node:child_process";
import { copyFile, mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { promisify } from "node:util";
import { gotoApp, loadSeededReplay, resetRuntimeState, startMission, waitForBasemapReady, waitForLinkOpen } from "../runtime";
import { hideSubtitle, moveMouseToHighlight, removeHighlight, showSubtitle } from "../tutorialHelpers";

export type DemoCase = "judge" | "payload" | "provenance" | "abstain" | "eclipse";

export type ProofJson = {
  demo: string;
  replay_id: string;
  model: string;
  provider: string;
  bbox: number[];
  latency_ms: number;
  raw_payload_bytes: number;
  alert_payload_bytes: number;
  payload_reduction_ratio: number | null;
  confidence: number;
  abstained: boolean;
  result: string;
  output_json: Record<string, unknown>;
  artifacts: {
    screenshot: string;
    evidence_frame: string;
    video: string;
    trace: string;
  };
};

const execFileAsync = promisify(execFile);
const MIN_DEMO_VIDEO_SECONDS = 8;

type DemoScenario = {
  intro: string;
  proofSubtitle: string;
  replayCellId?: string;
  preloadReplayId?: string;
  presetId?: string;
  presetLabel?: string;
  monitorButtonTestId?: string;
  monitorProofText?: string;
  launchMission?: boolean;
  initialBboxText?: string;
  taskText?: string;
  bbox?: number[];
  startDate?: string;
  endDate?: string;
  useCaseId?: string;
};

const DEMO_SCENARIOS: Record<DemoCase, DemoScenario> = {
  judge: {
    intro: "Judge Mode starts from a deterministic Rondonia replay and walks the strongest alert.",
    proofSubtitle: "The final screen shows satellite evidence, bbox, model output, latency, provenance, and compact JSON.",
    replayCellId: "sq_-10.0_-63.0",
    preloadReplayId: "rondonia_frontier_judge",
  },
  payload: {
    intro: "Payload proof scans Pakistan's Manchar Lake flood overflow and compares raw imagery against compact alert JSON.",
    proofSubtitle: "The important number is visible: the flood frame stays local, kilobytes go downlink.",
    presetId: "flood_manchar",
    presetLabel: "Manchar Lake flood",
    launchMission: true,
    initialBboxText: "67.63",
    taskText: "Find new surface water and overflow around Pakistan's Manchar Lake during the 2022 flood sequence.",
    bbox: [67.63, 26.31, 67.87, 26.55],
    startDate: "2022-06-15",
    endDate: "2022-09-15",
    useCaseId: "flood_extent",
  },
  provenance: {
    intro: "Provenance proof scans an Atacama mine and keeps source, capture time, bbox, prompt, and model together.",
    proofSubtitle: "The proof JSON is visible so the mining result is auditable without narration.",
    presetId: "mining_atacama",
    presetLabel: "Atacama open pit",
    launchMission: true,
    initialBboxText: "-69.11",
    taskText: "Detect Atacama open-pit mining expansion and separate persistent bare earth from seasonal vegetation loss.",
    bbox: [-69.115, -24.29, -69.035, -24.21],
    startDate: "2024-01-15",
    endDate: "2025-12-15",
    useCaseId: "mining_expansion",
  },
  abstain: {
    intro: "Abstain safety uses a Greenland ice mission to show that low-quality imagery does not become an unsupported answer.",
    proofSubtitle: "No timelapse or alert is transmitted when the quality gate fails.",
    presetId: "ice_greenland",
    presetLabel: "Greenland coast",
    launchMission: true,
    initialBboxText: "-51.13",
    taskText: "Compare same-season Greenland ice cap and glacier edge frames for true growth or retreat.",
    bbox: [-51.13, 69.1, -50.97, 69.26],
    startDate: "2024-01-15",
    endDate: "2025-10-15",
    useCaseId: "ice_cap_growth",
  },
  eclipse: {
    intro: "Orbital eclipse uses a maritime Suez mission: the app keeps working while the link is offline.",
    proofSubtitle: "Compact maritime alert packets queue locally, then flush when the link is restored.",
    presetId: "maritime_suez",
    presetLabel: "Suez channel",
    monitorButtonTestId: "maritime-monitor-button",
    monitorProofText: "Maritime Monitor",
    launchMission: true,
    initialBboxText: "32.50",
    taskText: "Review maritime vessel queueing near the Suez channel.",
    bbox: [32.5, 29.88, 32.58, 29.96],
    startDate: "2025-03-01",
    endDate: "2025-12-15",
    useCaseId: "maritime_activity",
  },
};

async function assertDemoVideoQuality(videoPath: string, demoName: string) {
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
  if (!Number.isFinite(durationSeconds) || durationSeconds < MIN_DEMO_VIDEO_SECONDS) {
    throw new Error(
      `${demoName} demo video is too short: ${durationSeconds.toFixed(2)}s. ` +
        `Expected at least ${MIN_DEMO_VIDEO_SECONDS}s.`,
    );
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
  const frameHashes = frameHashResult.stdout
    .split(/\r?\n/)
    .filter((line) => line && !line.startsWith("#"))
    .map((line) => {
      const parts = line.split(",");
      return parts[parts.length - 1]?.trim();
    })
    .filter(Boolean);
  const uniqueFrameCount = new Set(frameHashes).size;
  const minimumUniqueFrames = demoName === "abstain-safety" ? 3 : 5;
  if (uniqueFrameCount < minimumUniqueFrames) {
    throw new Error(
      `${demoName} demo video looks static: ${uniqueFrameCount} unique sampled frames. ` +
        `Expected at least ${minimumUniqueFrames}.`,
    );
  }
}

async function assertProofFrameQuality(framePath: string, demoName: string) {
  const statsResult = await execFileAsync("ffmpeg", [
    "-v",
    "error",
    "-i",
    framePath,
    "-vf",
    "scale=128:96,format=gray,signalstats,metadata=print:file=-",
    "-f",
    "null",
    "-",
  ]);
  const stats = new Map<string, number>();
  for (const line of statsResult.stdout.split(/\r?\n/)) {
    const match = line.match(/lavfi\.signalstats\.(YMIN|YAVG|YMAX)=([0-9.]+)/);
    if (match) {
      stats.set(match[1], Number(match[2]));
    }
  }

  const yMin = stats.get("YMIN");
  const yAvg = stats.get("YAVG");
  const yMax = stats.get("YMAX");
  if (yMin == null || yAvg == null || yMax == null) {
    throw new Error(`${demoName} proof frame quality stats were unavailable.`);
  }

  const luminanceRange = yMax - yMin;
  if (luminanceRange < 25 || yAvg < 8 || yAvg > 235) {
    throw new Error(
      `${demoName} proof frame looks blank or unusable: ` +
        `YMIN=${yMin.toFixed(1)} YAVG=${yAvg.toFixed(1)} YMAX=${yMax.toFixed(1)}.`,
    );
  }
}

export async function openDemo(page: Page, request: APIRequestContext, demoCase: DemoCase) {
  const scenario = DEMO_SCENARIOS[demoCase];
  await resetRuntimeState(request);
  if (scenario.preloadReplayId) {
    await loadSeededReplay(request, scenario.preloadReplayId);
  }
  if (scenario.taskText && scenario.bbox && scenario.startDate && scenario.endDate && scenario.useCaseId) {
    await startMission(request, {
      task_text: scenario.taskText,
      bbox: scenario.bbox,
      start_date: scenario.startDate,
      end_date: scenario.endDate,
      use_case_id: scenario.useCaseId,
    });
  }
  await gotoApp(page, `/?demo=1&demoCase=${demoCase}`);
  await waitForLinkOpen(page);
  await waitForBasemapReady(page);
  await showSubtitle(page, scenario.intro, 1_900);

  await expect(page.getByTestId("demo-caption")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("judge-mode-button")).toBeVisible();
  await page.getByTestId("tab-mission").click();

  if (scenario.presetId) {
    await expect(page.getByTestId("selected-mission-preset")).toContainText(scenario.presetLabel ?? "", {
      timeout: 15_000,
    });
    await expect(page.getByTestId("bbox-badge")).toContainText(scenario.initialBboxText ?? "", {
      timeout: 15_000,
    });
  }

  if (scenario.replayCellId) {
    await showSubtitle(page, "The deterministic replay is active before telemetry starts, so the video never opens on the generic scan.", 1_600);
    await expect(page.getByText("REPLAY ACTIVE: rondonia_frontier_judge")).toBeVisible({ timeout: 15_000 });

    await showSubtitle(page, "Open Logs and choose the evidence cell for this specific proof.", 1_500);
    await page.getByTestId("tab-logs").click();
    const alertButton = page.getByTestId("alert-button").filter({ hasText: scenario.replayCellId }).first();
    await expect(alertButton).toBeVisible({ timeout: 15_000 });
    await moveMouseToHighlight(page, `[data-testid='alert-button']:has-text("${scenario.replayCellId}")`);
    await alertButton.click();
    await removeHighlight(page);
    await expect(page.getByTestId("tab-inspect")).toBeVisible({ timeout: 10_000 });
    await showSubtitle(page, `Selected cell ${scenario.replayCellId}. The proof will use that cell's seeded WebM evidence.`, 1_700);
  } else if (scenario.presetId) {
    await showSubtitle(page, "Confirm the mission preset so this video covers the correct geography and task.", 1_600);
    const presetSelector = `[data-testid='mission-preset-${scenario.presetId}']`;
    await moveMouseToHighlight(page, presetSelector);
    await page.locator(presetSelector).click();
    await removeHighlight(page);
    await expect(page.getByTestId("selected-mission-preset")).toContainText(scenario.presetLabel ?? "", {
      timeout: 10_000,
    });

    if (scenario.monitorButtonTestId) {
      await showSubtitle(page, "Run the monitor preview before the proof screen so the video shows the mission logic.", 1_600);
      const monitorSelector = `[data-testid='${scenario.monitorButtonTestId}']`;
      await moveMouseToHighlight(page, monitorSelector);
      await page.locator(monitorSelector).click();
      await removeHighlight(page);
      const proofCard = page.getByTestId("monitor-proof-card");
      await expect(proofCard).toBeVisible({ timeout: 15_000 });
      await expect(proofCard).toContainText(scenario.monitorProofText ?? "");
      await showSubtitle(page, "The monitor returns deterministic evidence fields before any downlink story begins.", 1_800);
    }

    if (scenario.launchMission) {
      await showSubtitle(page, "Confirm the deterministic mission is active before Judge Mode binds the proof.", 1_500);
      const launchButton = page.getByRole("button", { name: "Launch Mission" });
      if ((await launchButton.count()) > 0 && await launchButton.first().isEnabled()) {
        await moveMouseToHighlight(page, "button:has-text('Launch Mission')");
        await launchButton.click();
        await removeHighlight(page);
      } else {
        await expect(page.getByRole("button", { name: "Mission In Progress" })).toBeVisible({ timeout: 10_000 });
      }
      await expect(page.getByText(/MISSION ACTIVE|Active Mission/).first()).toBeVisible({ timeout: 15_000 });
    }
  }

  await showSubtitle(page, "Open Judge Mode for the recorded proof panel.", 1_400);
  await moveMouseToHighlight(page, "[data-testid='judge-mode-button']");
  await page.getByTestId("judge-mode-button").click();
  await removeHighlight(page);
  await expect(page.getByTestId("judge-mode-panel")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("proof-json")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("proof-model")).toContainText("LFM2.5-VL-450M", { timeout: 30_000 });
  await showSubtitle(page, scenario.proofSubtitle, 2_000);
  await hideSubtitle(page);
}

export async function saveProofArtifacts(page: Page, demoName: string, testInfo: TestInfo): Promise<ProofJson> {
  const artifactDir = path.resolve("e2e", "artifacts", demoName);
  const screenshotPath = path.join(artifactDir, "final-screen.png");
  const evidenceFramePath = path.join(artifactDir, "evidence-frame.png");
  const proofPath = path.join(artifactDir, "proof.json");
  const videoPath = path.join(artifactDir, "video.webm");
  const docsVideoPath = path.resolve("..", "..", "docs", `${demoName}-demo.webm`);

  await mkdir(artifactDir, { recursive: true });
  await mkdir(path.dirname(docsVideoPath), { recursive: true });
  await page.waitForTimeout(8_000);
  await page.screenshot({ path: screenshotPath, fullPage: false });
  await page.getByTestId("satellite-frame").screenshot({ path: evidenceFramePath });
  await assertProofFrameQuality(evidenceFramePath, demoName);

  const proofText = await page.getByTestId("proof-json").textContent();
  const proof = JSON.parse(proofText ?? "{}") as ProofJson;

  const video = page.video();
  if (!video) {
    throw new Error("Playwright video recording is unavailable for this demo run.");
  }
  await page.close();
  await copyFile(await video.path(), videoPath);
  await copyFile(videoPath, docsVideoPath);
  await assertDemoVideoQuality(videoPath, demoName);

  proof.artifacts = {
    screenshot: "final-screen.png",
    evidence_frame: "evidence-frame.png",
    video: "video.webm",
    trace: "Playwright report trace.zip",
  };

  await writeFile(proofPath, `${JSON.stringify(proof, null, 2)}\n`, "utf8");
  await testInfo.attach("final-screen", { path: screenshotPath, contentType: "image/png" });
  await testInfo.attach("evidence-frame", { path: evidenceFramePath, contentType: "image/png" });
  await testInfo.attach("video", { path: videoPath, contentType: "video/webm" });
  await testInfo.attach("docs-video", { path: docsVideoPath, contentType: "video/webm" });
  await testInfo.attach("proof-json", { path: proofPath, contentType: "application/json" });
  return proof;
}
