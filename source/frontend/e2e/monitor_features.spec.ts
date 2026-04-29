import { test, expect } from "@playwright/test";
import { gotoApp, resetRuntimeState, waitForBasemapReady, waitForLinkOpen } from "./runtime";
import { API_BASE } from "./testUrls";

const SHOT_DIR = "e2e/screenshots";

test.describe("Monitor Feature Visual Proof", () => {
  test("monitor APIs expose lifeline, maritime, and eval contracts", async ({ request }) => {
    const assets = await request.get(`${API_BASE}/api/lifelines/assets`);
    expect(assets.ok()).toBeTruthy();
    const assetPayload = await assets.json();
    expect(assetPayload.count).toBeGreaterThanOrEqual(3);

    const lifeline = await request.post(`${API_BASE}/api/lifelines/monitor`, {
      data: {
        asset_id: "orbit_bridge_corridor",
        baseline_frame: {
          label: "before",
          date: "2025-01-01",
          source: "visual_test",
          asset_ref: "before.png",
        },
        current_frame: {
          label: "after",
          date: "2025-01-15",
          source: "visual_test",
          asset_ref: "after.png",
        },
        candidate: {
          event_type: "probable_access_obstruction",
          severity: "high",
          confidence: 0.88,
          bbox: [0.2, 0.25, 0.65, 0.75],
          civilian_impact: "public_mobility_disruption",
          why: "The current frame shows a bridge approach obstruction.",
          action: "downlink_now",
        },
      },
    });
    expect(lifeline.ok()).toBeTruthy();
    const lifelinePayload = await lifeline.json();
    expect(lifelinePayload.decision.action).toBe("downlink_now");
    expect(lifelinePayload.frames.pair_state.distinct_contextual_frames).toBe(true);

    const maritime = await request.post(`${API_BASE}/api/maritime/monitor`, {
      data: {
        lat: 29.92,
        lon: 32.54,
        timestamp: "2025-03-15",
        task_text: "Review maritime vessel queueing near a narrow channel.",
      },
    });
    expect(maritime.ok()).toBeTruthy();
    const maritimePayload = await maritime.json();
    expect(maritimePayload.investigation.directions).toHaveLength(4);
    expect(maritimePayload.use_case.id).toBe("maritime_activity");

    const evalResponse = await request.post(`${API_BASE}/api/lifelines/evaluate`, {
      data: {
        cases: [
          {
            candidate: {
              event_type: "probable_large_scale_disruption",
              severity: "high",
              confidence: 0.93,
              bbox: [0.1, 0.1, 0.5, 0.6],
              civilian_impact: "shipping_or_aid_disruption",
              why: "Current frame shows severe access loss at the logistics hub.",
              action: "downlink_now",
            },
            expected_action: "downlink_now",
          },
        ],
      },
    });
    expect(evalResponse.ok()).toBeTruthy();
    expect((await evalResponse.json()).downlink_now_recall).toBe(1);
  });

  test("visual proof: lifeline before/after monitor preview", async ({ page, request }) => {
    test.setTimeout(45_000);
    await resetRuntimeState(request);
    await gotoApp(page);
    await waitForLinkOpen(page);
    await waitForBasemapReady(page);
    await page.locator("[data-testid='tab-mission']").click();

    await expect(page.locator("[data-testid='monitor-template-panel']")).toBeVisible();
    await page.locator("[data-testid='lifeline-monitor-button']").click();
    const proofCard = page.locator("[data-testid='monitor-proof-card']");

    await expect(proofCard).toBeVisible({ timeout: 15_000 });
    await expect(proofCard).toContainText("Lifeline Monitor");
    await expect(proofCard).toContainText("downlink now");
    await expect(proofCard).toContainText("distinct frames");

    await page.screenshot({
      path: `${SHOT_DIR}/06-lifeline-monitor-preview.png`,
      fullPage: false,
    });
  });

  test("visual proof: maritime monitor preview", async ({ page, request }) => {
    test.setTimeout(45_000);
    await resetRuntimeState(request);
    await gotoApp(page);
    await waitForLinkOpen(page);
    await waitForBasemapReady(page);
    await page.locator("[data-testid='tab-mission']").click();

    await expect(page.locator("[data-testid='monitor-template-panel']")).toBeVisible();
    await page.locator("[data-testid='maritime-monitor-button']").click();
    const proofCard = page.locator("[data-testid='monitor-proof-card']");

    await expect(proofCard).toBeVisible({ timeout: 15_000 });
    await expect(proofCard).toContainText("Maritime Monitor");
    await expect(proofCard).toContainText("directions");
    await expect(proofCard).toContainText("STAC optional");
    await expect(page.locator("[data-testid='bbox-badge']")).toContainText("Active Area", { timeout: 10_000 });
    await page.waitForTimeout(1_500);

    await page.screenshot({
      path: `${SHOT_DIR}/07-maritime-monitor-preview.png`,
      fullPage: false,
    });
  });

  test("visual proof: Florida I-4 transportation mix mission preset", async ({ page, request }) => {
    test.setTimeout(45_000);
    await resetRuntimeState(request);
    await gotoApp(page);
    await waitForLinkOpen(page);
    await waitForBasemapReady(page);
    await page.locator("[data-testid='tab-mission']").click();

    await page.locator("[data-testid='mission-preset-traffic_i4_disney']").click();
    await expect(page.locator("[data-testid='selected-mission-preset']")).toContainText("I-4 interchange");
    await expect(page.locator("textarea")).toHaveValue(/transportation mix scan/);
    await expect(page.locator("[data-testid='bbox-badge']")).toContainText("-81.53", { timeout: 10_000 });
    await page.locator("[data-testid='selected-mission-preset']").scrollIntoViewIfNeeded();
    await page.waitForTimeout(1_500);

    await page.screenshot({
      path: `${SHOT_DIR}/08-traffic-i4-preview.png`,
      fullPage: false,
    });
  });

  test("visual proof: Highway 82 wildfire mission preset", async ({ page, request }) => {
    test.setTimeout(45_000);
    await resetRuntimeState(request);
    await gotoApp(page);
    await waitForLinkOpen(page);
    await waitForBasemapReady(page);
    await page.locator("[data-testid='tab-mission']").click();

    await page.locator("[data-testid='mission-preset-wildfire_highway82']").click();
    await expect(page.locator("[data-testid='selected-mission-preset']")).toContainText("Highway 82 fire");
    await expect(page.locator("textarea")).toHaveValue(/Highway 82 wildfire/);
    await expect(page.locator("[data-testid='bbox-badge']")).toContainText("-81.92", { timeout: 10_000 });
    await page.locator("[data-testid='selected-mission-preset']").scrollIntoViewIfNeeded();
    await page.waitForTimeout(1_500);

    await page.screenshot({
      path: `${SHOT_DIR}/09-highway-82-wildfire-preview.png`,
      fullPage: false,
    });
  });

  test("visual proof: timestamped SPC future fire watch preset", async ({ page, request }) => {
    test.setTimeout(45_000);
    await resetRuntimeState(request);
    await gotoApp(page);
    await waitForLinkOpen(page);
    await waitForBasemapReady(page);
    await page.locator("[data-testid='tab-mission']").click();

    await page.locator("[data-testid='mission-preset-wildfire_future_spc_high_plains']").click();
    await expect(page.locator("[data-testid='selected-mission-preset']")).toContainText("SPC D2 High Plains");
    await expect(page.locator("textarea")).toHaveValue(/SPC Day 2 critical fire-weather/);
    await expect(page.locator("[data-testid='bbox-badge']")).toContainText("-104.90", { timeout: 10_000 });
    await page.locator("[data-testid='selected-mission-preset']").scrollIntoViewIfNeeded();
    await page.waitForTimeout(1_500);

    await page.screenshot({
      path: `${SHOT_DIR}/09b-spc-future-fire-watch-preview.png`,
      fullPage: false,
    });
  });

  test("visual proof: Greenland ice/snow extent mission preset", async ({ page, request }) => {
    test.setTimeout(45_000);
    await resetRuntimeState(request);
    await gotoApp(page);
    await waitForLinkOpen(page);
    await waitForBasemapReady(page);
    await page.locator("[data-testid='tab-mission']").click();

    await page.locator("[data-testid='mission-preset-ice_greenland']").click();
    await expect(page.locator("[data-testid='selected-mission-preset']")).toContainText("Greenland coast");
    await expect(page.locator("textarea")).toHaveValue(/Greenland edge snow and ice extent/);
    await expect(page.locator("[data-testid='bbox-badge']")).toContainText("-51.13", { timeout: 10_000 });
    await page.locator("[data-testid='selected-mission-preset']").scrollIntoViewIfNeeded();
    await page.waitForTimeout(1_500);

    await page.screenshot({
      path: `${SHOT_DIR}/10-greenland-ice-preview.png`,
      fullPage: false,
    });
  });
});
