import { test, expect, type Page } from "@playwright/test";
import { execFile } from "node:child_process";
import { stat } from "node:fs/promises";
import path from "node:path";
import { promisify } from "node:util";
import { gotoApp, openMapContextMenu, resetRuntimeState, waitForBasemapReady, waitForLinkOpen, waitForNextPaint } from "./runtime";

const execFileAsync = promisify(execFile);

function backendCommandEnv(): NodeJS.ProcessEnv {
  if (process.env.CI && !process.env.UV_PROJECT_ENVIRONMENT) {
    return { ...process.env, UV_PROJECT_ENVIRONMENT: ".venv-linux" };
  }
  return process.env;
}

type VisualStory = {
  presetId: string;
  expectedPresetText: string;
  prompt: string;
  label: string;
  confidence: number;
  colorKey: string;
  boxes: {
    label: string;
    confidence: number;
    colorKey: string;
    bbox: [number, number, number, number];
  }[];
  screenshotName: string;
};

const STORIES: VisualStory[] = [
  {
    presetId: "urban_delhi",
    expectedPresetText: "Delhi NCR",
    prompt: "Find urban structure areas",
    label: "structure area",
    confidence: 0.88,
    colorKey: "structure",
    boxes: [
      { label: "structure area", confidence: 0.88, colorKey: "structure", bbox: [0.438, 0.412, 0.472, 0.454] },
      { label: "structure area", confidence: 0.85, colorKey: "structure", bbox: [0.485, 0.386, 0.518, 0.426] },
      { label: "roof cluster", confidence: 0.82, colorKey: "structure", bbox: [0.355, 0.462, 0.43, 0.515] },
      { label: "large roof area", confidence: 0.79, colorKey: "structure", bbox: [0.582, 0.404, 0.655, 0.475] },
    ],
    screenshotName: "visual-overlay-fixture-urban-structures.png",
  },
  {
    presetId: "wildfire_highway82",
    expectedPresetText: "Highway 82 fire",
    prompt: "Find smoke and burn-scar areas",
    label: "smoke-shadow area",
    confidence: 0.82,
    colorKey: "hazard",
    boxes: [
      { label: "smoke-shadow area", confidence: 0.82, colorKey: "hazard", bbox: [0.4, 0.35, 0.56, 0.52] },
      { label: "burn-scar candidate area", confidence: 0.78, colorKey: "hazard", bbox: [0.24, 0.52, 0.39, 0.67] },
      { label: "road-impact area", confidence: 0.71, colorKey: "lifeline", bbox: [0.58, 0.56, 0.70, 0.66] },
    ],
    screenshotName: "visual-overlay-fixture-fireline.png",
  },
  {
    presetId: "maritime_suez",
    expectedPresetText: "Suez channel",
    prompt: "Find vessel groups, vessel queue areas, and shipping container clusters",
    label: "vessel queue area",
    confidence: 0.84,
    colorKey: "vessel",
    boxes: [
      { label: "vessel queue area", confidence: 0.84, colorKey: "vessel", bbox: [0.42, 0.43, 0.54, 0.56] },
      { label: "channel traffic area", confidence: 0.82, colorKey: "vessel", bbox: [0.57, 0.24, 0.65, 0.32] },
      { label: "shipping container cluster", confidence: 0.78, colorKey: "cargo", bbox: [0.62, 0.38, 0.74, 0.50] },
      { label: "crane area", confidence: 0.73, colorKey: "infrastructure", bbox: [0.68, 0.23, 0.76, 0.32] },
    ],
    screenshotName: "visual-overlay-fixture-port.png",
  },
  {
    presetId: "traffic_i4_disney",
    expectedPresetText: "I-4 interchange",
    prompt: "Find road disruption areas",
    label: "road disruption area",
    confidence: 0.79,
    colorKey: "lifeline",
    boxes: [
      { label: "road disruption area", confidence: 0.79, colorKey: "lifeline", bbox: [0.43, 0.38, 0.55, 0.55] },
      { label: "vehicle queue area", confidence: 0.74, colorKey: "vehicle", bbox: [0.36, 0.52, 0.48, 0.63] },
      { label: "road corridor", confidence: 0.72, colorKey: "lifeline", bbox: [0.57, 0.43, 0.68, 0.56] },
    ],
    screenshotName: "visual-overlay-fixture-road.png",
  },
];

async function setBboxNearMapCenter(page: Page) {
  await openMapContextMenu(page);
  await page.getByText("◫ Set Mission BBox Here").click();
}

async function runStory(page: Page, story: VisualStory) {
  await page.route("**/api/vlm/grounding", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        results: story.boxes.map((box) => ({
            label: box.label,
            bbox: box.bbox,
            bbox_format: "unit_xyxy",
            confidence: box.confidence,
            color_key: box.colorKey,
            source_model: "replay_fixture",
            prompt: story.prompt,
            runtime_truth_mode: "replay",
            imagery_origin: "cached_api",
            scoring_basis: "visual_only",
          })),
        provenance: {
          runtime_truth_mode: "replay",
          imagery_origin: "cached_api",
          scoring_basis: "visual_only",
          model: "replay_fixture",
        },
      }),
    });
  });

  await gotoApp(page);
  await waitForLinkOpen(page);
  await waitForBasemapReady(page);
  await page.getByTestId("tab-mission").click();
  await page.getByTestId(`mission-preset-${story.presetId}`).click();
  await expect(page.getByTestId("selected-mission-preset")).toContainText(story.expectedPresetText);
  await waitForNextPaint(page, 8);

  await setBboxNearMapCenter(page);
  const input = page.getByPlaceholder("Find: structure cluster, vessel group, possible flaring region");
  await input.fill(story.prompt);
  await input.press("Enter");

  await expect(page.getByTestId("vlm-grounding-result").filter({ hasText: story.label }).first()).toBeVisible({ timeout: 10_000 });
  await expect(page.getByTestId("vlm-object-box-legend")).toContainText(story.label);
  await waitForNextPaint(page, 70);

  const canvas = page.locator(".maplibregl-canvas").first();
  const canvasBox = await canvas.boundingBox();
  expect(canvasBox).not.toBeNull();
  if (story.presetId === "urban_delhi") {
    await page.mouse.move(canvasBox!.x + canvasBox!.width * 0.5, canvasBox!.y + canvasBox!.height * 0.45);
    await page.mouse.wheel(0, -1300);
    await waitForNextPaint(page, 24);
  }
  const tooltip = page.getByTestId("vlm-box-tooltip");
  let sawTooltip = false;
  for (const point of [
    { x: 0.448, y: 0.472 },
    { x: 0.510, y: 0.449 },
    { x: 0.370, y: 0.533 },
    { x: 0.638, y: 0.478 },
    { x: 0.445, y: 0.493 },
    { x: 0.575, y: 0.468 },
    { x: 0.46, y: 0.44 },
    { x: 0.5, y: 0.5 },
    { x: 0.43, y: 0.5 },
    { x: 0.53, y: 0.48 },
  ]) {
    await page.mouse.move(canvasBox!.x + canvasBox!.width * point.x, canvasBox!.y + canvasBox!.height * point.y);
    await waitForNextPaint(page, 2);
    if (await tooltip.isVisible()) {
      sawTooltip = true;
      break;
    }
  }
  expect(sawTooltip).toBeTruthy();
  const screenshot = await page.getByTestId("map-visualizer").screenshot({
    path: `test-results/visual-overlay-fixtures/${story.screenshotName}`,
  });
  expect(screenshot.length).toBeGreaterThan(50_000);

  await page.unroute("**/api/vlm/grounding");
}

test.describe.skip("retired visual overlay fixture stories", () => {
  test.describe.configure({ mode: "serial" });

  for (const story of STORIES) {
    test(`draws ${story.label} overlay fixture over ${story.expectedPresetText}`, async ({ page, request }) => {
      await resetRuntimeState(request);
      await runStory(page, story);
    });
  }

  test("refreshes promoted story plates after visual fixture pass", async () => {
    test.setTimeout(120_000);
    const backendDir = path.resolve("..", "backend");
    const repoRoot = path.resolve("..", "..");
    await execFileAsync("uv", ["run", "--no-sync", "python", "scripts/build_visual_story_proofs.py", "--offline"], {
      cwd: backendDir,
      env: backendCommandEnv(),
    });

    const expectedOutputs = [
      path.join(repoRoot, "docs", "media", "story-plates", "story-object-evidence-port.png"),
      path.join(repoRoot, "source", "backend", "assets", "seeded_data", "visual_story_frames", "story_plates", "story-object-evidence-houses.png"),
      path.join(repoRoot, "source", "backend", "assets", "seeded_data", "visual_story_frames", "story_plates", "story-object-evidence-shelters.png"),
      path.join(repoRoot, "source", "backend", "assets", "seeded_data", "visual_story_frames", "story_plates", "story-object-evidence-fireline.png"),
      path.join(repoRoot, "source", "backend", "assets", "seeded_data", "visual_story_frames", "story_plates", "story-object-evidence-road.png"),
      path.join(repoRoot, "source", "backend", "assets", "seeded_data", "visual_story_frames", "story_plates", "story-object-evidence-debris.png"),
    ];

    for (const outputPath of expectedOutputs) {
      const outputStats = await stat(outputPath);
      expect(outputStats.size).toBeGreaterThan(50_000);
    }
  });
});
