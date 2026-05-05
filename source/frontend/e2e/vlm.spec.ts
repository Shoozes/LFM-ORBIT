import { test, expect, type APIRequestContext } from "@playwright/test";
import { gotoApp, resetRuntimeState, waitForBasemapReady, waitForLinkOpen, waitForNextPaint } from "./runtime";
import { API_BASE } from "./testUrls";

async function startEvidenceMission(request: APIRequestContext) {
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
}

test.describe("Mission evidence", () => {
  test("runs mission targets and renders evidence boxes", async ({ page, request }) => {
    await resetRuntimeState(request);
    await startEvidenceMission(request);

    await page.route("**/api/vlm/grounding/batch", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          results: [
            {
              label: "dark smoke",
              bbox: [0.4, 0.35, 0.56, 0.52],
              bbox_format: "unit_xyxy",
              confidence: 0.82,
              color_key: "hazard",
              source_model: "replay_fixture",
              prompt: "Find dark smoke",
              runtime_truth_mode: "replay",
              imagery_origin: "cached_api",
              scoring_basis: "visual_only",
            },
          ],
          summary: {
            target_pack_id: "fireline",
            total_boxes: 1,
            provenance: {
              runtime_truth_mode: "replay",
              imagery_origin: "cached_api",
              scoring_basis: "visual_only",
              model: "replay_fixture",
            },
          },
        }),
      });
    });

    await gotoApp(page);
    await waitForLinkOpen(page);
    await waitForBasemapReady(page);
    await page.getByTestId("tab-mission").click();
    await expect(page.getByTestId("bbox-badge")).toContainText("-81.92", { timeout: 10_000 });
    await page.getByTestId("open-evidence-tools").click();

    await expect(page.getByTestId("mission-evidence-panel")).toContainText("Mission Evidence");
    await expect(page.getByTestId("vlm-mission-targets")).toContainText("dark smoke");
    await page.getByTestId("vlm-run-mission-targets").click();

    const result = page.getByTestId("vlm-grounding-result").filter({ hasText: "dark smoke" });
    await expect(result).toBeVisible({ timeout: 10_000 });
    await expect(result).toHaveAttribute("title", /Confidence: 0\.82/);
    await expect(page.getByTestId("vlm-object-box-legend")).toContainText("dark smoke");

    await result.hover();
    await waitForNextPaint(page, 2);
    const tooltip = page.getByTestId("vlm-result-tooltip");
    await expect(tooltip).toContainText("dark smoke", { timeout: 10_000 });
    await expect(tooltip).toContainText("replay_fixture");
  });

  test("keeps evidence UI focused on mission targets only", async ({ page, request }) => {
    await resetRuntimeState(request);
    await startEvidenceMission(request);
    await gotoApp(page);
    await waitForLinkOpen(page);
    await waitForBasemapReady(page);

    await page.getByTestId("tab-mission").click();
    await expect(page.getByTestId("mission-panel-tab-plan")).toBeVisible();
    await expect(page.getByTestId("mission-panel-tab-replay")).toBeVisible();
    await expect(page.getByTestId("mission-panel-tab-targets")).toHaveCount(0);
    await expect(page.getByTestId("mission-panel-tab-monitors")).toHaveCount(0);

    await page.getByTestId("open-evidence-tools").click();
    await expect(page.getByTestId("mission-evidence-panel")).toContainText("Mission Evidence");
    await expect(page.getByText("Visual Q&A")).toHaveCount(0);
    await expect(page.getByText("Captioning")).toHaveCount(0);
    await expect(page.getByPlaceholder(/Find:/)).toHaveCount(0);
  });
});
