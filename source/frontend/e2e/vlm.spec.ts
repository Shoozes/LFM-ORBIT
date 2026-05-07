import { test, expect, type APIRequestContext, type Page } from "@playwright/test";
import { readFileSync } from "fs";
import { resolve } from "path";
import { gotoApp, loadSeededReplay, resetRuntimeState, startMission, waitForBasemapReady, waitForLinkOpen } from "./runtime";
import { API_BASE } from "./testUrls";

function seededTimelapseDataUrl() {
  const videoPath = resolve(process.cwd(), "../backend/assets/seeded_data/nasa_aa01bc81.webm");
  return `data:video/webm;base64,${readFileSync(videoPath).toString("base64")}`;
}

async function routeMissionTimelapse(page: Page) {
  const video_b64 = seededTimelapseDataUrl();
  await page.route("**/api/timelapse/generate", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        video_b64,
        frames_count: 13,
        format: "webm",
        source: "nasa_gibs",
        provider: "nasa_gibs",
        runtime_truth_mode: "live",
        imagery_origin: "cached_api",
        scoring_basis: "context_timelapse",
        provenance: {
          label: "Related mission timelapse",
          provider: "nasa_gibs",
          kind: "test_fixture",
        },
      }),
    });
  });
}

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

test.describe("Mission target pack UX", () => {
  test("keeps target packs out of the normal Mission controls", async ({ page, request }) => {
    await resetRuntimeState(request);
    await startEvidenceMission(request);

    await gotoApp(page);
    await waitForLinkOpen(page);
    await waitForBasemapReady(page);

    await expect(page.getByTestId("map-area-tools")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId("map-area-bbox")).toContainText("-81.92", { timeout: 10_000 });
    await page.getByTestId("tab-mission").click();
    await expect(page.getByTestId("mission-panel-tab-plan")).toBeVisible();
    await expect(page.getByTestId("mission-panel-tab-replay")).toBeVisible();
    await expect(page.getByTestId("mission-panel-tab-targets")).toHaveCount(0);
    await expect(page.getByTestId("mission-panel-tab-monitors")).toHaveCount(0);
    await expect(page.getByTestId("open-evidence-tools")).toHaveCount(0);
    await expect(page.getByTestId("mission-evidence-panel")).toHaveCount(0);
    await expect(page.getByText("Visual Q&A")).toHaveCount(0);
    await expect(page.getByText("Captioning")).toHaveCount(0);
  });

  test("keeps proof mode explicit and mission-scoped", async ({ page, request }) => {
    await resetRuntimeState(request);
    await gotoApp(page);
    await waitForLinkOpen(page);

    await expect(page.getByTestId("ground-agent-nav-proof")).toBeDisabled();
    await expect(page.getByTestId("proof-mode-panel")).toHaveCount(0);

    await startEvidenceMission(request);
    await page.reload();
    await waitForLinkOpen(page);
    await waitForBasemapReady(page);
    await expect(page.getByTestId("ground-agent-nav-proof")).toBeEnabled({ timeout: 10_000 });
    await page.getByTestId("ground-agent-nav-proof").click();
    await expect(page.getByTestId("proof-mode-panel")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText("Critical Minerals Expansion Watch")).toHaveCount(0);
  });

  test("live Florida firewatch proof does not reuse stale mining replay media", async ({ page, request }) => {
    test.setTimeout(90_000);
    await resetRuntimeState(request);
    await routeMissionTimelapse(page);
    await loadSeededReplay(request, "atacama_mining_replay");

    await gotoApp(page);
    await waitForLinkOpen(page);
    await expect(page.getByTestId("ground-agent-nav-proof")).toBeEnabled({ timeout: 10_000 });
    await page.getByTestId("ground-agent-nav-proof").click();
    await expect(page.getByTestId("proof-mode-panel")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("demo-title")).toContainText("Atacama Mining Replay proof");
    await page.getByRole("button", { name: "Close" }).click();

    await startMission(request, {
      task_text: "Run Florida Fire/Drought Readiness Watch over a North Florida corridor. Treat this as candidate evidence until source-backed imagery confirms smoke, active fire, or burn scar.",
      bbox: [-83.2, 29.0, -81.3, 30.7],
      start_date: "2026-04-05",
      end_date: "2026-05-05",
      use_case_id: "wildfire",
      target_pack_id: "fireline",
    });
    await page.reload();
    await waitForLinkOpen(page);

    await expect(page.getByTestId("ground-agent-nav-proof")).toBeEnabled({ timeout: 10_000 });
    await page.getByTestId("ground-agent-nav-proof").click();
    await expect(page.getByTestId("proof-mode-panel")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("demo-title")).toContainText("Florida Fire/Drought Readiness Watch");
    await expect(page.getByTestId("proof-timelapse-video")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("timelapse-integrity")).toContainText("Related mission timelapse");
    await expect(page.getByTestId("proof-json")).toContainText('"use_case_id": "wildfire"');
    await expect(page.getByTestId("proof-json")).toContainText("fireline");
    await expect(page.getByTestId("proof-json")).not.toContainText("atacama");
    await expect(page.getByTestId("proof-json")).not.toContainText("critical minerals");
  });

  test("chat minerals proof replay replaces a prior Florida firewatch mission", async ({ page, request }) => {
    test.setTimeout(90_000);
    await resetRuntimeState(request);
    await startMission(request, {
      task_text: "Run Florida Fire/Drought Readiness Watch over a North Florida corridor. Treat this as candidate evidence until source-backed imagery confirms smoke, active fire, or burn scar.",
      bbox: [-83.2, 29.0, -81.3, 30.7],
      start_date: "2026-04-05",
      end_date: "2026-05-05",
      use_case_id: "wildfire",
      target_pack_id: "fireline",
    });

    await gotoApp(page);
    await waitForLinkOpen(page);
    await waitForBasemapReady(page);

    const chatInput = page.getByPlaceholder("Request replay, mission pack, link action...");
    await chatInput.fill("Run critical minerals mission");
    await page.getByRole("button", { name: "Send" }).click();

    const proposal = page.getByTestId("ground-agent-proposal-card").last();
    await expect(proposal).toContainText("Load replay: Critical Minerals Expansion Watch", { timeout: 15_000 });
    await expect(proposal).toContainText("atacama_mining_replay");
    await proposal.getByRole("button", { name: "Run Replay" }).click();

    await expect(page.getByText("REPLAY ACTIVE: atacama_mining_replay")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("tab-inspect")).toHaveClass(/border-zinc-900/);

    await page.getByTestId("tab-agents").click();
    await page.getByTestId("ground-agent-nav-proof").click();
    await expect(page.getByTestId("proof-mode-panel")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("demo-title")).toContainText("Atacama Mining Replay proof");
    await expect(page.getByTestId("proof-json")).toContainText('"replay_id": "atacama_mining_replay"');
    await expect(page.getByTestId("proof-json")).toContainText("critical_minerals");
    await expect(page.getByTestId("proof-json")).not.toContainText("fireline");
    await expect(page.getByTestId("proof-json")).not.toContainText("Florida Fire/Drought");
  });

  test("completed live mission exposes result CTAs into logs and proof", async ({ page, request }) => {
    await resetRuntimeState(request);
    await routeMissionTimelapse(page);
    const completedMission = {
      id: 9001,
      task_text: "Run Florida Fire/Drought Readiness Watch over a tiny North Florida test cell. Treat this as candidate evidence until source-backed imagery confirms smoke, active fire, or burn scar.",
      bbox: [-82.75, 29.25, -82.74, 29.26],
      start_date: "2026-04-05",
      end_date: "2026-05-05",
      status: "active",
      mission_mode: "live",
      replay_id: null,
      summary: "Completed test firewatch pass.",
      use_case_id: "wildfire",
      target_pack_id: "fireline",
      object_targets: [],
      use_case_confidence: 1,
      use_case_decision: null,
      cells_scanned: 4,
      flags_found: 0,
      created_at: "2026-05-05T00:00:00.000Z",
    };
    await page.route("**/api/mission/current", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ mission: completedMission }),
      });
    });
    await page.route("**/api/alerts/recent**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          region_id: "test",
          alerts: [{
            event_id: "stale-mining-alert",
            region_id: "atacama",
            cell_id: "sq_-24.2_-69.0",
            change_score: 0.91,
            confidence: 0.88,
            priority: "high",
            reason_codes: ["critical_minerals"],
            payload_bytes: 224,
            observation_source: "replay",
            analysis_summary: "Stale Atacama mining alert from an earlier mission.",
          }],
        }),
      });
    });
    const imported = await request.post(`${API_BASE}/api/replay/snapshot/import`, {
      data: {
        format: "orbit_runtime_snapshot_v1",
        schema_version: 1,
        active_mission: completedMission,
        alerts: [],
        gallery: [],
        pins: [],
        messages: [],
        metrics: {
          total_cells_scanned: 4,
          total_alerts_emitted: 0,
          total_payload_bytes: 0,
          total_bandwidth_saved_mb: 7.36,
          latest_discard_ratio: 1,
        },
      },
    });
    expect(imported.ok()).toBeTruthy();

    await gotoApp(page);
    await waitForLinkOpen(page);
    await waitForBasemapReady(page);
    await expect(page.getByTestId("scan-complete-notice")).toBeVisible({ timeout: 45_000 });
    await expect(page.getByTestId("scan-complete-notice")).toContainText("Review results");
    await expect(page.getByTestId("scan-complete-open-first-result")).toHaveText("Review Summary");

    await page.getByTestId("scan-complete-open-logs").click();
    await expect(page.getByTestId("tab-logs")).toHaveClass(/border-zinc-900/);

    await page.getByTestId("tab-mission").click();
    await expect(page.getByTestId("mission-complete-summary")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId("mission-complete-open-first-result")).toHaveText("Review Summary");
    await page.getByTestId("mission-complete-open-proof").click();
    await expect(page.getByTestId("proof-mode-panel")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("demo-title")).toContainText("Florida Fire/Drought Readiness Watch");
    await expect(page.getByTestId("proof-timelapse-video")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("proof-mission-result-overlay")).toContainText("Nothing interesting found");
    await expect(page.getByTestId("proof-cv-box")).toHaveCount(0);
    await expect(page.getByText(/scan completion/i)).toBeVisible();
    await expect(page.getByTestId("proof-json")).toContainText('"status": "no_flags_retained"');
  });

  test("does not let stale demo query override an active live mission", async ({ page, request }) => {
    await resetRuntimeState(request);
    await startEvidenceMission(request);

    await gotoApp(page, "/?demo=1&demoCase=forest");
    await waitForLinkOpen(page);
    await waitForBasemapReady(page);

    await expect(page.getByTestId("map-area-bbox")).toContainText("-81.92, 31.14, -81.76, 31.30");
    await page.getByTestId("tab-mission").click();
    await expect(page.getByText("Run Southeast Fireline Watch.")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId("demo-caption")).toHaveCount(0);
    await expect(page.getByTestId("selected-mission-preset")).toHaveCount(0);
  });
});
