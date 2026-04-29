import { test, expect, type APIRequestContext, type Page } from "@playwright/test";
import { readFileSync } from "fs";
import { resolve } from "path";
import { API_BASE } from "./testUrls";
import { gotoApp, openMapContextMenu, resetRuntimeState, waitForBasemapReady, waitForLinkOpen } from "./runtime";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function waitForAlerts(page: Page, minAlerts = 1, timeoutMs = 45_000) {
  // Switch to Logs Tab if not already there to monitor the Recent Alerts stat counter
  if ((await page.locator("[data-testid='tab-logs']").getAttribute("class")).indexOf("border-zinc-900") === -1) {
    await page.locator("[data-testid='tab-logs']").click();
  }

  await expect(async () => {
    const alertCount = await page.locator("[data-testid='alert-button']").count();
    expect(alertCount).toBeGreaterThanOrEqual(minAlerts);
  }).toPass({ timeout: timeoutMs });

  await expect(page.locator("[data-testid='alert-button']").first()).toBeVisible({ timeout: 5000 });
}

async function waitForScanArtifacts(page: Page, timeoutMs = 60_000) {
  if ((await page.locator("[data-testid='tab-logs']").getAttribute("class")).indexOf("border-zinc-900") === -1) {
    await page.locator("[data-testid='tab-logs']").click();
  }

  await expect(async () => {
    const alertCount = await page.locator("[data-testid='alert-button']").count();
    const markerCount = await page.locator(".map-pin-bubble, .maplibregl-marker").count();
    expect(alertCount > 0 || markerCount > 0).toBeTruthy();
  }).toPass({ timeout: timeoutMs });
}

function seededTimelapseDataUrl() {
  const videoPath = resolve(process.cwd(), "../backend/assets/seeded_data/nasa_aa01bc81.webm");
  return `data:video/webm;base64,${readFileSync(videoPath).toString("base64")}`;
}

async function waitForSettingsApiReady(request: APIRequestContext) {
  await expect(async () => {
    const responses = await Promise.all([
      request.get(`${API_BASE}/api/provider/status`),
      request.get(`${API_BASE}/api/simsat/status`),
      request.get(`${API_BASE}/api/analysis/status`),
      request.get(`${API_BASE}/api/depth/status`),
    ]);

    for (const response of responses) {
      expect(response.ok()).toBeTruthy();
    }
  }).toPass({ timeout: 30_000, intervals: [500, 1000, 2000] });
}

async function waitForAgentBusNote(request: APIRequestContext, pattern: RegExp) {
  await expect(async () => {
    const response = await request.get(`${API_BASE}/api/agent/bus/dialogue?limit=120`);
    expect(response.ok()).toBeTruthy();
    const body = await response.json() as { messages?: Array<{ payload?: { note?: string } }> };
    const notes = (body.messages ?? []).map((message) => message.payload?.note ?? "");
    expect(notes.some((note) => pattern.test(note))).toBeTruthy();
  }).toPass({ timeout: 15_000, intervals: [300, 750, 1500] });
}

// ---------------------------------------------------------------------------
// Phase 1: API smoke tests
// ---------------------------------------------------------------------------

test.describe("Phase 1 – API smoke tests", () => {
  test("backend health returns ok", async ({ request }) => {
    const res = await request.get(`${API_BASE}/api/health`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.status).toBe("ok");
    expect(body.region_id).toBe("amazonas_region_alpha");
    expect(body.observation_mode).toBeTruthy();
  });

  test("provider status endpoint works", async ({ request }) => {
    const res = await request.get(`${API_BASE}/api/provider/status`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.active_provider).toBeTruthy();
  });

  test("metrics summary endpoint works", async ({ request }) => {
    await resetRuntimeState(request);
    const res = await request.get(`${API_BASE}/api/metrics/summary`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.region_id).toBe("amazonas_region_alpha");
    expect(typeof body.total_cells_scanned).toBe("number");
  });

  test("simsat status endpoint works", async ({ request }) => {
    const res = await request.get(`${API_BASE}/api/simsat/status`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.simsat_base_url).toBeTruthy();
    expect(typeof body.simsat_available).toBe("boolean");
  });
});

// ---------------------------------------------------------------------------
// Phase 2: Frontend loads and renders
// ---------------------------------------------------------------------------

test.describe("Phase 2 – Frontend renders", () => {
  test("app loads with title and scanner HUD", async ({ page }) => {
    await gotoApp(page);
    await expect(page.getByText("Mission").first()).toBeVisible();
    await expect(page.getByText("New Mission", { exact: true })).toBeVisible({ timeout: 10_000 });
  });



  test("WebSocket connects and link goes open", async ({ page }) => {
    await gotoApp(page);
    await waitForLinkOpen(page);
  });

  test("basemap renders with satellite attribution", async ({ page }) => {
    await gotoApp(page);
    await expect(page.getByText("SATELLITE BASEMAP")).toBeVisible();
    await expect(page.getByText("Not part of detection or scoring")).toBeVisible();
  });

  test("backend scan heartbeat broadcasts pins to the map", async ({ page }) => {
    await gotoApp(page);
    await waitForLinkOpen(page);
    await waitForScanArtifacts(page, 60_000);

    // Once alerts arrive, the map should render at least one marker/pin for a flagged cell.
    await expect(page.locator(".map-pin-bubble, .maplibregl-marker").first()).toBeVisible({ timeout: 15_000 });
  });

  test("map pin API failures are visible to the operator", async ({ page }) => {
    await page.route("**/api/map/pins", async (route) => {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ error: "map pins unavailable" }),
      });
    });

    await gotoApp(page);

    await expect(page.getByText("Map pins unavailable: HTTP 503")).toBeVisible({ timeout: 8_000 });
  });
});

// ---------------------------------------------------------------------------
// Phase 3: Alerts and evidence
// ---------------------------------------------------------------------------

test.describe("Phase 3 – Alerts and temporal evidence", () => {
  test("alerts appear in sidebar when anomalies detected", async ({ page }) => {
    await gotoApp(page);
    await waitForLinkOpen(page);
    await waitForAlerts(page, 1);
  });

  test("clicking alert shows temporal evidence panel", async ({ page }) => {
    await gotoApp(page);
    await waitForLinkOpen(page);
    await waitForAlerts(page, 1);
    const firstAlert = page.locator("[data-testid='alert-button']").first();
    await firstAlert.click();
    await expect(page.getByText("Temporal Evidence", { exact: true })).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("Before Window", { exact: true })).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("After Window", { exact: true })).toBeVisible();
    await expect(page.getByText("Signal Deltas", { exact: true })).toBeVisible();
  });

  test("selected alert shows observation source label", async ({ page }) => {
    await gotoApp(page);
    await waitForLinkOpen(page);
    await waitForAlerts(page, 1);
    const firstAlert = page.locator("[data-testid='alert-button']").first();
    await firstAlert.click();
    await expect(page.getByText("Source:").first()).toBeVisible({ timeout: 5_000 });
  });

  test("flagged examples counter increments during scan", async ({ page }) => {
    await gotoApp(page);
    await waitForLinkOpen(page);
    await page.waitForTimeout(3_000);
    if ((await page.locator("[data-testid='tab-logs']").getAttribute("class")).indexOf("border-zinc-900") === -1) {
      await page.locator("[data-testid='tab-logs']").click();
    }
    await expect(async () => {
      const text = await page.getByText("Flagged Examples").locator("..").locator("p").nth(1).innerText();
      expect(parseInt(text, 10)).toBeGreaterThan(0);
    }).toPass({ timeout: 15_000 });
  });

  test("demo evidence disclaimer is visible on selected alert", async ({ page }) => {
    await gotoApp(page);
    await waitForLinkOpen(page);
    await waitForAlerts(page, 1);
    const firstAlert = page.locator("[data-testid='alert-button']").first();
    await firstAlert.click();
    await expect(page.getByText("does not claim final ground truth")).toBeVisible({ timeout: 5_000 });
  });
});

// ---------------------------------------------------------------------------
// Phase 4: Settings panel
// ---------------------------------------------------------------------------

test.describe("Phase 4 – Settings and provider display", () => {
  test("settings panel opens and shows provider status", async ({ page }) => {
    await gotoApp(page);
    await page.locator("[data-testid='tab-settings']").click();
    await expect(page.getByText("Provider Status")).toBeVisible({ timeout: 10_000 });
    await expect(
      page.getByText("Active Provider").or(page.getByText("Backend Offline").first())
    ).toBeVisible({ timeout: 20_000 });
  });

  test("settings panel shows provider availability", async ({ page }) => {
    await gotoApp(page);
    await page.locator("[data-testid='tab-settings']").click();
    await expect(page.getByText("Provider Status")).toBeVisible({ timeout: 10_000 });
  });

  test("settings panel shows sentinel credential status", async ({ page }) => {
    await gotoApp(page);
    await page.locator("[data-testid='tab-settings']").click();
    await expect(page.getByPlaceholder("Sentinel Client ID")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByPlaceholder("Sentinel Client Secret")).toBeVisible({ timeout: 20_000 });
  });

  test("settings panel shows SimSat API section", async ({ page }) => {
    await gotoApp(page);
    await page.locator("[data-testid='tab-settings']").click();
    await expect(page.getByText("SimSat API")).toBeVisible({ timeout: 20_000 });
  });

  test("settings panel shows optional Depth Anything V3 toggle", async ({ page }) => {
    await gotoApp(page);
    await page.locator("[data-testid='tab-settings']").click();
    await expect(page.getByText("Depth Anything V3")).toBeVisible({ timeout: 20_000 });

    const toggle = page.getByLabel("Enable");
    await expect(toggle).toBeVisible();
    await expect(page.getByText(/depth_anything_3 package not installed|disabled|enabled, not loaded/i).first()).toBeVisible();
  });

  test("settings tab closes when switching to another tab", async ({ page }) => {
    await gotoApp(page);
    await page.locator("[data-testid='tab-settings']").click();
    await expect(page.getByText("PROVIDER STATUS")).toBeVisible({ timeout: 10_000 });
    await page.locator("[data-testid='tab-mission']").click();
    await expect(page.getByText("PROVIDER STATUS")).not.toBeVisible({ timeout: 5_000 });
  });
});

// ---------------------------------------------------------------------------
// Phase 4.5: Bottom Toolbar Modules
// ---------------------------------------------------------------------------

test.describe("Phase 4.5 – Sidebar Tabs Navigation", () => {
  test("mission tab shows mission control panel", async ({ page }) => {
    await gotoApp(page);
    await page.locator("[data-testid='tab-mission']").click();
    await expect(page.getByText("New Mission")).toBeVisible({ timeout: 5_000 });
  });

  test("agents tab shows agent dialogue bus", async ({ page }) => {
    await gotoApp(page);
    await page.locator("[data-testid='tab-agents']").click();
    await expect(page.getByTestId("header-agent-bus")).toBeVisible({ timeout: 5_000 });
  });

  test("logs tab shows alerts panel", async ({ page }) => {
    await gotoApp(page);
    await page.locator("[data-testid='tab-logs']").click();
    await expect(page.getByText("Recent Alerts")).toBeVisible({ timeout: 5_000 });
  });

  test("logs tab surfaces pipeline integrity metrics", async ({ page }) => {
    await gotoApp(page);
    await page.locator("[data-testid='tab-logs']").click();
    await expect(page.getByText("Pipeline Integrity")).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("Scene Rejects")).toBeVisible();
    await expect(page.getByText("Low Coverage")).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// Phase 4.75: Replay flow
// ---------------------------------------------------------------------------

test.describe("Phase 4.75 – Seeded replay flow", () => {
  test("cached replay loads into inspect and historical dialogue", async ({ page, request }) => {
    await resetRuntimeState(request);
    await gotoApp(page);
    await waitForLinkOpen(page);
    await page.locator("[data-testid='tab-mission']").click();

    await expect(page.getByTestId("fast-replay-panel")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId("load-replay-rondonia_frontier_judge")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId("rescan-replay-rondonia_frontier_judge")).toBeVisible();
    await expect(page.getByTestId("load-replay-manchar_flood_replay")).toBeVisible();
    await expect(page.getByTestId("load-replay-singapore_maritime_replay")).toBeVisible();

    await page.getByTestId("load-replay-rondonia_frontier_judge").click();
    await expect(page.getByText("REPLAY ACTIVE: rondonia_frontier_judge")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Seeded Replay Evidence", { exact: true })).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("sq_-10.0_-63.0").first()).toBeVisible({ timeout: 10_000 });

    await page.locator("[data-testid='tab-agents']").click();
    await expect(page.getByText("Historical replay trace loaded")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole("button", { name: "Inject" })).toBeDisabled();

    await page.locator("[data-testid='tab-mission']").click();
    await expect(page.getByText("Replay Mission · rondonia_frontier_judge")).toBeVisible({ timeout: 10_000 });
    await page.getByRole("button", { name: "Exit Replay" }).click();
    await expect(page.getByText("REPLAY ACTIVE: rondonia_frontier_judge")).not.toBeVisible({ timeout: 10_000 });

    await page.getByTestId("rescan-replay-rondonia_frontier_judge").click();
    await expect(page.getByText("Live rescan started from replay metadata")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(/Active Mission #/)).toBeVisible({ timeout: 10_000 });
  });
});

// ---------------------------------------------------------------------------
// Phase 5: Full scan cycle and data integrity
// ---------------------------------------------------------------------------

test.describe("Phase 5 – Full scan cycle", () => {
  test("full cycle completes and flagged examples appear", async ({ page }) => {
    await gotoApp(page);
    await waitForLinkOpen(page);
    await page.waitForTimeout(8_000);
    if ((await page.locator("[data-testid='tab-logs']").getAttribute("class")).indexOf("border-zinc-900") === -1) {
      await page.locator("[data-testid='tab-logs']").click();
    }
    await expect(async () => {
      const text = await page.getByText("Flagged Examples").locator("..").locator("p").nth(1).innerText();
      expect(parseInt(text, 10)).toBeGreaterThan(0);
    }).toPass({ timeout: 15_000 });
  });



  test("alerts API returns data after scanning", async ({ request }) => {
    await new Promise((r) => setTimeout(r, 8_000));
    const res = await request.get(`${API_BASE}/api/alerts/recent?limit=10`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.alerts.length).toBeGreaterThan(0);
    const alert = body.alerts[0];
    expect(alert.event_id).toBeTruthy();
    expect(alert.cell_id).toBeTruthy();
    expect(typeof alert.change_score).toBe("number");
    expect(typeof alert.confidence).toBe("number");
    expect(alert.priority).toBeTruthy();
    expect(alert.reason_codes).toBeInstanceOf(Array);
  });

  test("metrics summary shows scan progress after cycles", async ({ request }) => {
    await new Promise((r) => setTimeout(r, 8_000));
    const res = await request.get(`${API_BASE}/api/metrics/summary`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.total_cells_scanned).toBeGreaterThan(0);
    expect(body.total_alerts_emitted).toBeGreaterThan(0);
    expect(body.total_bandwidth_saved_mb).toBeGreaterThan(0);
  });
});

// ---------------------------------------------------------------------------
// Phase 6 – Visual evidence capture
// ---------------------------------------------------------------------------

test.describe("Phase 6 – Visual evidence capture", () => {
  test("capture full app with scan in progress", async ({ page }) => {
    await gotoApp(page);
    await waitForLinkOpen(page);
    await waitForScanArtifacts(page, 45_000);
    // Brief settle time for map tiles and animations to render
    await page.waitForTimeout(1_000);
    await page.screenshot({ path: "e2e/screenshots/app-scan-in-progress.png" });
  });

  test("capture selected alert with evidence", async ({ page }) => {
    await gotoApp(page);
    await waitForLinkOpen(page);
    await waitForAlerts(page, 1);
    const firstAlert = page.locator("[data-testid='alert-button']").first();
    await firstAlert.click();
    // Wait for the full evidence panel to populate
    await expect(page.getByText("Before Window", { exact: true })).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("After Window", { exact: true })).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("Signal Deltas", { exact: true })).toBeVisible({ timeout: 5_000 });
    // Wait for imagery to finish fetching (source label replaces "fetching…")
    await expect(page.getByText("fetching…")).not.toBeVisible({ timeout: 15_000 });
    // Brief settle time for images to paint
    await page.waitForTimeout(500);
    await page.screenshot({ path: "e2e/screenshots/alert-temporal-evidence.png" });
  });

  test("capture settings panel", async ({ page, request }) => {
    await waitForSettingsApiReady(request);
    await resetRuntimeState(request);
    await waitForSettingsApiReady(request);
    await gotoApp(page);
    await waitForLinkOpen(page);
    await waitForBasemapReady(page);
    await page.locator("[data-testid='tab-settings']").click();
    await expect(page.getByText("Provider Status")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Active Provider")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText("Some settings data could not be refreshed")).not.toBeVisible();
    await expect(page.getByText("Backend Offline")).not.toBeVisible();
    await expect(page.getByText("Model Tiers")).toBeVisible({ timeout: 20_000 });
    await page.screenshot({ path: "e2e/screenshots/settings-provider-status.png" });
  });
});
// ---------------------------------------------------------------------------
// Phase 7 – AI analysis endpoints and UI
// ---------------------------------------------------------------------------

test.describe("Phase 7 – AI analysis", () => {
  test("analysis status endpoint returns model info", async ({ request }) => {
    const res = await request.get(`${API_BASE}/api/analysis/status`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.default_model).toBe("offline_lfm_v1");
    expect(body.models).toBeTruthy();
    expect(body.models["offline_lfm_v1"]).toBeTruthy();
    expect(body.models["offline_lfm_v1"].available).toBe(true);
    expect(typeof body.satellite_inference_loaded).toBe("boolean");
  });

  test("analysis alert endpoint returns offline LFM result", async ({ request }) => {
    const res = await request.post(`${API_BASE}/api/analysis/alert`, {
      data: {
        change_score: 0.52,
        confidence: 0.76,
        reason_codes: ["ndvi_drop", "nir_drop"],
        before_window: {
          label: "2024-06",
          ndvi: 0.71,
          nbr: 0.58,
          nir: 0.68,
          red: 0.10,
          swir: 0.18,
          quality: 0.92,
          flags: [],
        },
        after_window: {
          label: "2025-06",
          ndvi: 0.42,
          nbr: 0.33,
          nir: 0.44,
          red: 0.14,
          swir: 0.22,
          quality: 0.88,
          flags: [],
        },
        observation_source: "semi_real_loader_v1",
        demo_forced_anomaly: false,
      },
    });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.model).toBe("offline_lfm_v1");
    expect(body.severity).toBeTruthy();
    expect(body.summary).toBeTruthy();
    expect(body.findings).toBeInstanceOf(Array);
  });

  test("settings panel shows LOCAL MODEL section", async ({ page }) => {
    await gotoApp(page);
    await page.locator("[data-testid='tab-settings']").click();
    await expect(page.getByText("Local Model")).toBeVisible();
    await expect(page.getByText("Model Tiers")).toBeVisible();
  });

  test("analyze button appears on selected alert", async ({ page }) => {
    await gotoApp(page);
    await waitForLinkOpen(page);
    await waitForAlerts(page, 1);
    const firstAlert = page.locator("[data-testid='alert-button']").first();
    await firstAlert.click();
    await expect(page.locator("[data-testid='analyze-button']")).toBeVisible({ timeout: 5_000 });
  });

  test("clicking analyze button produces LFM analysis", async ({ page }) => {
    await gotoApp(page);
    await waitForLinkOpen(page);
    await waitForAlerts(page, 1);
    const firstAlert = page.locator("[data-testid='alert-button']").first();
    await firstAlert.click();
    await expect(page.locator("[data-testid='analyze-button']")).toBeVisible({ timeout: 5_000 });
    await page.locator("[data-testid='analyze-button']").click();
    await expect(page.getByText("offline_lfm_v1", { exact: true }).first()).toBeVisible({ timeout: 30_000 });
  });
});

// ---------------------------------------------------------------------------
// Phase 9 – Interaction Modules and FFMpeg Context Evaluation
// ---------------------------------------------------------------------------

test.describe("Phase 9 - Context Module and Timelapse Validation", () => {
  test("context menu drops on right click", async ({ page }) => {
    await gotoApp(page);
    await waitForLinkOpen(page);
    await waitForBasemapReady(page);

    await openMapContextMenu(page);

    // Validate Context Menu opens securely
    await expect(page.getByText("Spatial Options")).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("◫ Set Mission BBox Here")).toBeVisible();
    await expect(page.getByText("▷ Generate Temporal Timelapse")).toBeVisible();
    await expect(page.getByText("◈ Agent Video Evaluation")).toBeVisible();

    // Capture Visual Baseline
    await page.waitForTimeout(500);
    await page.screenshot({ path: "e2e/screenshots/context-menu-deployed.png" });
  });

  test("triggering timelapse drops temporal popup", async ({ page }) => {
    const video_b64 = seededTimelapseDataUrl();
    await page.route("**/api/timelapse/generate", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          video_b64,
          frames_count: 8,
          format: "webm",
          provenance: {
            kind: "replay_cache",
            legacy_kind: "seeded_cache",
            label: "Cached real API timelapse",
          },
        }),
      });
    });

    await gotoApp(page);
    await waitForLinkOpen(page);
    await waitForBasemapReady(page);

    await openMapContextMenu(page);

    // Construct timelapse execution payload
    const timelapseBtn = page.getByText("▷ Generate Temporal Timelapse");
    await expect(timelapseBtn).toBeVisible({ timeout: 5_000 });
    await timelapseBtn.click();

    // Make sure Timelapse modal hooks capture sequence FFMpeg payload rendering
    await expect(page.getByText(/Orbital Timelapse/i)).toBeVisible({ timeout: 10_000 });
    await expect(page.locator("video")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Cached real API timelapse")).toBeVisible({ timeout: 5_000 });
    await page.waitForFunction(() => {
      const video = document.querySelector("video");
      return video instanceof HTMLVideoElement && video.readyState >= 2;
    });

    await page.waitForTimeout(2000);
    await page.screenshot({ path: "e2e/screenshots/ffmpeg-timelapse-viewer.png" });
  });

  test("timelapse viewer surfaces API error payloads", async ({ page }) => {
    await page.route("**/api/timelapse/generate", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          video_b64: "",
          frames_count: 0,
          format: "none",
          error: "Synthetic timelapse failure.",
        }),
      });
    });

    await gotoApp(page);
    await waitForLinkOpen(page);
    await waitForBasemapReady(page);

    await openMapContextMenu(page);
    await page.getByText("▷ Generate Temporal Timelapse").click();

    await expect(page.getByText("Synthetic timelapse failure.")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole("button", { name: "Retry Request" })).toBeVisible();
  });

  test("triggering agent evaluation dispatches API payload to bus", async ({ page, request }) => {
    await resetRuntimeState(request);
    await gotoApp(page);
    await waitForLinkOpen(page);
    await waitForBasemapReady(page);

    await openMapContextMenu(page, { xRatio: 0.56, yRatio: 0.56 });

    const agentEValBtn = page.getByText("◈ Agent Video Evaluation");
    await expect(agentEValBtn).toBeVisible({ timeout: 5_000 });
    await agentEValBtn.click();

    // Ensure agent dialog expands to track the injected bus query representing the visual multi-model pass.
    const queryPattern = /Analyze orbital timeframe for coords/i;
    await waitForAgentBusNote(request, queryPattern);
    const busQuery = page.getByText(queryPattern).last();
    await busQuery.scrollIntoViewIfNeeded();
    await expect(busQuery).toBeVisible({ timeout: 10_000 });

    await page.waitForTimeout(1000);
    await page.screenshot({ path: "e2e/screenshots/agent-multimodality-evaluation.png" });
  });
});
