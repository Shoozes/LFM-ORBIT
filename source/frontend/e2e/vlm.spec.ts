import { test, expect } from "@playwright/test";
import { gotoApp, openMapContextMenu, resetRuntimeState, waitForBasemapReady, waitForLinkOpen, waitForNextPaint } from "./runtime";
import { API_BASE } from "./testUrls";

test.describe("Visual evidence tools E2E test", () => {
  test("edits mission object targets and runs all mission targets", async ({ page, request }) => {
    await resetRuntimeState(request);
    const start = await request.post(`${API_BASE}/api/mission/start`, {
      data: {
        task_text: "Run Southeast Fireline Watch.",
        bbox: [-81.916, 31.143, -81.756, 31.303],
        start_date: "2026-04-01",
        end_date: "2026-04-28",
        use_case_id: "wildfire",
        target_pack_id: "fireline",
      },
    });
    expect(start.ok()).toBeTruthy();

    await page.route("**/api/vlm/grounding/batch", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          results: [
            {
              id: "box_docked_vessel_group_001",
              label: "docked-vessel group",
              bbox: [0.38, 0.34, 0.56, 0.52],
              bbox_format: "unit_xyxy",
              confidence: 0.84,
              color_key: "vessel",
              source_model: "replay_fixture",
              prompt: "Find docked-vessel groups along berth edges",
              runtime_truth_mode: "replay",
              imagery_origin: "cached_api",
              scoring_basis: "visual_only",
              count_quality: "activity_region",
            },
          ],
          summary: {
            target_pack_id: "fireline",
            total_boxes: 1,
            counts_by_label: { "docked-vessel group": 1 },
            top_boxes: [],
            provenance: {
              runtime_truth_mode: "replay",
              imagery_origin: "cached_api",
              scoring_basis: "visual_only",
              model: "replay_fixture",
            },
          },
          target_count: 5,
        }),
      });
    });

    await gotoApp(page);
    await waitForLinkOpen(page);
    await waitForBasemapReady(page);
    await page.getByTestId("tab-mission").click();
    await page.getByTestId("mission-panel-tab-targets").click();

    await expect(page.getByTestId("object-targets-panel")).toContainText("dark smoke");
    const smokeChip = page.getByTestId("object-target-chip").filter({ hasText: "dark smoke" });
    const smokeToggle = smokeChip.getByTestId("object-target-toggle");
    await expect(smokeToggle).toHaveAttribute("aria-pressed", "true");
    await smokeToggle.click();
    await expect(smokeToggle).toHaveAttribute("aria-pressed", "false");
    await smokeToggle.click();
    await expect(smokeToggle).toHaveAttribute("aria-pressed", "true");

    await page.getByTestId("object-target-input").fill("vehicle queue");
    await page.getByTestId("object-target-add").click();
    await expect(page.getByTestId("object-targets-panel")).toContainText("vehicle queue");
    await page.getByTestId("object-target-pack-name").fill("Mission Fireline E2E");
    await page.getByTestId("object-target-save-pack").click();
    await expect(page.getByTestId("target-pack-select")).toHaveValue("mission_fireline_e2e");

    await page.getByTestId("target-pack-select").selectOption("port");
    await expect(page.getByTestId("object-targets-panel")).toContainText("docked-vessel group");
    await page.getByTestId("object-target-input").fill("yard crane");
    await page.getByTestId("object-target-add").click();
    await expect(page.getByTestId("object-targets-panel")).toContainText("yard crane");
    await page.getByTestId("object-target-reset-pack").click();
    await expect(page.getByTestId("object-targets-panel")).not.toContainText("yard crane");

    await openMapContextMenu(page);
    await page.getByText("◫ Set Mission BBox Here").click();
    await expect(page.getByTestId("vlm-mission-targets")).toContainText("docked-vessel group");

    await page.getByTestId("vlm-run-mission-targets").click();
    const result = page.getByTestId("vlm-grounding-result").filter({ hasText: "docked-vessel group" });
    await expect(result).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId("vlm-object-box-legend")).toContainText("docked-vessel group");
    await waitForNextPaint(page, 3);
    const canvas = page.locator(".maplibregl-canvas").first();
    const canvasBox = await canvas.boundingBox();
    expect(canvasBox).not.toBeNull();
    await page.mouse.move(canvasBox!.x + canvasBox!.width * 0.5, canvasBox!.y + canvasBox!.height * 0.5);
    await waitForNextPaint(page, 60);
    await page.screenshot({ path: "e2e/screenshots/mission-object-targets.png" });
  });

  test("shows glowing object evidence legend and tooltip for grounded boxes", async ({ page, request }) => {
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
              confidence: 0.82,
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
    await openMapContextMenu(page);
    await page.getByText("◫ Set Mission BBox Here").click();

    await expect(page.getByText("Visual Evidence Tools")).toBeVisible();
    const input = page.getByPlaceholder("Find: structure cluster, vessel group, possible flaring region");
    await input.fill("Find dark smoke");
    await input.press("Enter");

    const result = page.getByTestId("vlm-grounding-result").filter({ hasText: "dark smoke" });
    await expect(result).toBeVisible({ timeout: 10_000 });
    await expect(result).toHaveAttribute("title", /Confidence: 0\.82/);
    await expect(page.getByTestId("vlm-object-box-legend")).toContainText("dark smoke");

    await result.hover();
    await waitForNextPaint(page, 2);

    const tooltip = page.getByTestId("vlm-result-tooltip");
    await expect(tooltip).toContainText("dark smoke", { timeout: 10_000 });
    await expect(tooltip).toContainText("Confidence");
    await expect(tooltip).toContainText("replay_fixture");
    await page.screenshot({ path: "e2e/screenshots/vlm-object-box-tooltip.png" });
  });

  test("mounts visual evidence panel, sets bbox via context menu, executes search", async ({ page, request }) => {
    await resetRuntimeState(request);
    await gotoApp(page);
    await waitForLinkOpen(page);
    await waitForBasemapReady(page);
    await page.getByTestId("tab-mission").click();
    await page.getByTestId("mission-preset-traffic_i4_disney").click();
    await expect(page.getByTestId("selected-mission-preset")).toContainText("I-4 interchange");
    await openMapContextMenu(page);
    await page.getByText("◫ Set Mission BBox Here").click();

    await page.getByTestId("tab-mission").click();
    await expect(page.getByText("Visual Evidence Tools")).toBeVisible();

    const gInput = page.getByPlaceholder("Find: structure cluster, vessel group, possible flaring region");
    await expect(gInput).toBeVisible({ timeout: 5_000 });
    await gInput.fill("Find road corridor");
    await gInput.press("Enter");

    await expect(
      page.getByText(/road|Find road corridor|No matches found\./i).first(),
    ).toBeVisible({ timeout: 15_000 });

    await page.getByTestId("vlm-target-vessel-group").click();
    await expect(gInput).toHaveValue("Find vessel group");
    await expect(page.getByText("No matches found.")).toBeVisible({ timeout: 15_000 });

    const vqaInput = page.getByPlaceholder("What land cover is visible?");
    await vqaInput.fill("What land cover is visible?");
    await vqaInput.press("Enter");
    await expect(page.getByTestId("vlm-vqa-answer")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(/road corridor|water bodies|managed vegetation|Unable to answer precisely|Unknown\./i).first()).toBeVisible({ timeout: 15_000 });

    await page.getByRole("button", { name: "Generate" }).click();
    await expect(page.getByTestId("vlm-caption-result")).toBeVisible({ timeout: 15_000 });
    await expect(
      page.getByText(/Florida road corridor|satellite view|developed land|Describe the scene/i).first(),
    ).toBeVisible({ timeout: 15_000 });

    await page.screenshot({ path: "e2e/screenshots/vlm-panel-results.png" });
  });
});
