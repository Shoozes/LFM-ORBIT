import { test, expect, type Page } from "@playwright/test";
import {
  gotoApp,
  loadSeededReplay,
  openMapContextMenu,
  resetRuntimeState,
  waitForBasemapReady,
  waitForLinkOpen,
  waitForNextPaint,
} from "./runtime";

async function setBboxFromMapCenter(page: Page) {
  await openMapContextMenu(page);
  await page.getByText("◫ Set Mission BBox Here").click();
}

async function expect3DCanvasHasVisibleGeometry(page: Page) {
  const stats = await page.getByTestId("map-3d-canvas").evaluate((node) => {
    const canvas = node as HTMLCanvasElement;
    const gl = canvas.getContext("webgl2") ?? canvas.getContext("webgl");
    if (!gl || canvas.width <= 0 || canvas.height <= 0) {
      return { sampled: 0, nonDark: 0, uniqueColors: 0 };
    }

    const pixel = new Uint8Array(4);
    const colors = new Set<string>();
    let sampled = 0;
    let nonDark = 0;
    const fractions = [0.18, 0.3, 0.42, 0.54, 0.66, 0.78];

    for (const xFraction of fractions) {
      for (const yFraction of fractions) {
        const x = Math.min(canvas.width - 1, Math.max(0, Math.floor(canvas.width * xFraction)));
        const y = Math.min(canvas.height - 1, Math.max(0, Math.floor(canvas.height * yFraction)));
        gl.readPixels(x, y, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
        sampled += 1;
        const luminance = pixel[0] + pixel[1] + pixel[2];
        if (pixel[3] > 0 && luminance > 45) nonDark += 1;
        colors.add(`${Math.floor(pixel[0] / 16)}:${Math.floor(pixel[1] / 16)}:${Math.floor(pixel[2] / 16)}`);
      }
    }

    return { sampled, nonDark, uniqueColors: colors.size };
  });

  expect(stats.sampled).toBeGreaterThan(0);
  expect(stats.nonDark).toBeGreaterThan(6);
  expect(stats.uniqueColors).toBeGreaterThan(1);
}

test.describe("3D context view", () => {
  test("opens no-auth satellite terrain using the active bbox and CV boxes", async ({ page, request }) => {
    await resetRuntimeState(request);
    await page.route("**/api/vlm/grounding", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          results: [
            {
              label: "dark smoke",
              bbox: [0.4, 0.35, 0.56, 0.52],
              bbox_format: "unit_xyxy",
              confidence: 0.86,
              color_key: "hazard",
              source_model: "replay_fixture",
              prompt: "Find dark smoke",
              runtime_truth_mode: "replay",
              imagery_origin: "cached_api",
              scoring_basis: "visual_only",
            },
          ],
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
    await setBboxFromMapCenter(page);

    const input = page.getByPlaceholder("Find: structure cluster, vessel group, possible flaring region");
    await input.fill("Find dark smoke");
    await input.press("Enter");
    await expect(page.getByTestId("vlm-object-box-legend")).toContainText("dark smoke");

    const toggle = page.getByTestId("map-3d-toggle");
    await expect(toggle).toBeVisible();
    await expect(toggle).toHaveAttribute("aria-pressed", "false");
    await toggle.click();

    const panel = page.getByTestId("map-3d-panel");
    await expect(panel).toBeVisible();
    await expect(panel).toContainText("3D satellite terrain");
    await expect(panel).toContainText("no auth");
    await expect(panel).toContainText("This 3D view is terrain/context, not a satellite acquisition frame.");
    await expect(panel).toContainText("Relief boost:");
    await expect(page.getByTestId("map-3d-relief-mesh-label")).toContainText("Local relief mesh: on");
    await expect(panel).toContainText("Sentinel-2 cloudless by EOX");
    await expect(panel).toContainText("Objects found: 1");
    await expect(page.getByTestId("map-3d-canvas")).toBeVisible({ timeout: 15_000 });
    await waitForNextPaint(page, 5);
    await expect3DCanvasHasVisibleGeometry(page);

    await page.getByTestId("map-3d-ai-toggle").check();
    await expect(page.getByTestId("map-3d-ai-summary")).toContainText(/Depth Anything|Fast mode|Canvas cue/i, {
      timeout: 15_000,
    });

    await page.getByTestId("map-3d-cv-chip").first().hover();
    await expect(page.getByTestId("map-3d-object-tooltip")).toContainText("dark smoke", { timeout: 10_000 });
    await page.screenshot({ path: "e2e/screenshots/map-3d-context-view.png", fullPage: true });

    await page.getByTestId("map-3d-close").click();
    await expect(panel).toBeHidden();
  });

  test("uses replay bbox, warns on timeline mismatch, and closes with Escape", async ({ page, request }) => {
    await resetRuntimeState(request);
    await loadSeededReplay(request, "greenland_ice_snow_extent_replay");

    await gotoApp(page);
    await waitForLinkOpen(page);
    await waitForBasemapReady(page);
    await expect(page.getByText(/REPLAY ACTIVE:/)).toBeVisible({ timeout: 15_000 });

    const toggle = page.getByTestId("map-3d-toggle");
    await expect(toggle).toBeVisible();
    await expect(toggle).toHaveAttribute("aria-pressed", "false");
    await toggle.click();

    const panel = page.getByTestId("map-3d-panel");
    await expect(panel).toBeVisible();
    await expect(panel).toContainText("Timeline: 2025-12-15");
    await expect(panel).toContainText("The 3D view is newer than the selected timeline date.");
    await expect(panel).toContainText("This 3D view is terrain/context, not a satellite acquisition frame.");
    await expect(page.getByTestId("map-3d-relief-mesh-label")).toContainText("Local relief mesh: on");
    await expect(page.getByTestId("map-3d-terrain-slider")).toHaveValue("3.2");
    await expect(page.getByTestId("map-3d-canvas")).toBeVisible({ timeout: 15_000 });
    await waitForNextPaint(page, 5);
    await expect3DCanvasHasVisibleGeometry(page);

    await page.keyboard.press("Escape");
    await expect(panel).toBeHidden();
    await expect(toggle).toHaveAttribute("aria-pressed", "false");
  });

  test("shows a recoverable error state when 3D initialization fails", async ({ page, request }) => {
    await resetRuntimeState(request);
    await gotoApp(page);
    await waitForLinkOpen(page);
    await waitForBasemapReady(page);
    await page.evaluate(() => window.localStorage.setItem("lfm_force_3d_error", "1"));
    await page.getByTestId("tab-mission").click();
    await setBboxFromMapCenter(page);

    await page.getByTestId("map-3d-toggle").click();
    const panel = page.getByTestId("map-3d-panel");
    await expect(panel).toBeVisible();
    await expect(panel).toContainText("Forced 3D context error for renderer diagnostics.");

    await page.evaluate(() => window.localStorage.removeItem("lfm_force_3d_error"));
    await page.getByTestId("map-3d-close").click();
    await expect(panel).toBeHidden();
  });
});
