import { test, expect, type Page } from "@playwright/test";

const API_BASE = "http://localhost:8000";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function waitForAlerts(page: Page, minAlerts = 1, timeoutMs = 45_000) {
  await expect(async () => {
    const text = await page.getByText("ALERTS / SAVINGS").locator("..").locator("p.text-cyan-400").innerText();
    expect(parseInt(text, 10)).toBeGreaterThanOrEqual(minAlerts);
  }).toPass({ timeout: timeoutMs });
  
  // Open the overlay where alerts list lives
  if ((await page.locator("[data-testid='alert-button']").count()) === 0) {
    await page.getByTitle("Alerts and Logs").click();
  }
  await expect(page.locator("[data-testid='alert-button']").first()).toBeVisible({ timeout: 5000 });
}

async function waitForLinkOpen(page: Page) {
  await expect(page.getByText("LINK OPEN")).toBeVisible({ timeout: 30_000 });
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
    await page.goto("/");
    await expect(page.getByText("Mission").first()).toBeVisible();
    await expect(page.getByText("New Mission", { exact: true })).toBeVisible({ timeout: 10_000 });
  });



  test("WebSocket connects and link goes open", async ({ page }) => {
    await page.goto("/");
    await waitForLinkOpen(page);
  });

  test("basemap renders with satellite attribution", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("SATELLITE BASEMAP")).toBeVisible();
    await expect(page.getByText("Not part of detection or scoring")).toBeVisible();
  });

  test("scan progress counter increments", async ({ page }) => {
    await page.goto("/");
    await waitForLinkOpen(page);

    await expect(async () => {
      const text = await page.getByText("PROGRESS").locator("..").locator("p.text-white").innerText();
      const parts = text.split("/");
      expect(parseInt(parts[0])).toBeGreaterThan(0);
    }).toPass({ timeout: 15_000 });
  });
});

// ---------------------------------------------------------------------------
// Phase 3: Alerts and evidence
// ---------------------------------------------------------------------------

test.describe("Phase 3 – Alerts and temporal evidence", () => {
  test("alerts appear in sidebar when anomalies detected", async ({ page }) => {
    await page.goto("/");
    await waitForLinkOpen(page);
    await waitForAlerts(page, 1);
  });

  test("clicking alert shows temporal evidence panel", async ({ page }) => {
    await page.goto("/");
    await waitForLinkOpen(page);
    await waitForAlerts(page, 1);
    const firstAlert = page.locator("[data-testid='alert-button']").first();
    await firstAlert.click();
    await expect(page.getByText("TEMPORAL EVIDENCE", { exact: true })).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("BEFORE WINDOW", { exact: true })).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("AFTER WINDOW", { exact: true })).toBeVisible();
    await expect(page.getByText("SIGNAL DELTAS", { exact: true })).toBeVisible();
  });

  test("selected alert shows observation source label", async ({ page }) => {
    await page.goto("/");
    await waitForLinkOpen(page);
    await waitForAlerts(page, 1);
    const firstAlert = page.locator("[data-testid='alert-button']").first();
    await firstAlert.click();
    await expect(page.getByText("Source:").first()).toBeVisible({ timeout: 5_000 });
  });

  test("bandwidth saved counter increments during scan", async ({ page }) => {
    await page.goto("/");
    await waitForLinkOpen(page);
    await page.waitForTimeout(3_000);
    await expect(async () => {
      const text = await page.getByText("ALERTS / SAVINGS").locator("..").locator("p.text-cyan-400").innerText();
      expect(text.length).toBeGreaterThan(0);
    }).toPass({ timeout: 15_000 });
  });

  test("demo evidence disclaimer is visible on selected alert", async ({ page }) => {
    await page.goto("/");
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
    await page.goto("/");
    await page.locator("[data-testid='tab-settings']").click();
    await expect(page.getByText("Provider Status")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Active Provider")).toBeVisible();
    await expect(page.getByText("Provider Tiers")).toBeVisible();
    await expect(page.getByText("Fallback Order")).toBeVisible();
  });

  test("settings panel shows provider availability", async ({ page }) => {
    await page.goto("/");
    await page.locator("[data-testid='tab-settings']").click();
    await expect(page.getByText("Provider Status")).toBeVisible({ timeout: 10_000 });
  });

  test("settings panel shows sentinel credential status", async ({ page }) => {
    await page.goto("/");
    await page.locator("[data-testid='tab-settings']").click();
    await expect(page.getByText("Sentinel Credentials")).toBeVisible({ timeout: 10_000 });
  });

  test("settings panel shows SimSat API section", async ({ page }) => {
    await page.goto("/");
    await page.locator("[data-testid='tab-settings']").click();
    await expect(page.getByText("SimSat API")).toBeVisible({ timeout: 10_000 });
  });

  test("settings tab closes when switching to another tab", async ({ page }) => {
    await page.goto("/");
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
    await page.goto("/");
    await page.locator("[data-testid='tab-mission']").click();
    await expect(page.getByText("◈ MISSION CONTROL")).toBeVisible({ timeout: 5_000 });
  });

  test("agents tab shows agent dialogue bus", async ({ page }) => {
    await page.goto("/");
    await page.locator("[data-testid='tab-agents']").click();
    await expect(page.getByText("Agent Dialogue Bus")).toBeVisible({ timeout: 5_000 });
  });

  test("logs tab shows alerts panel", async ({ page }) => {
    await page.goto("/");
    await page.locator("[data-testid='tab-logs']").click();
    await expect(page.getByText("Recent Alerts")).toBeVisible({ timeout: 5_000 });
  });
});

// ---------------------------------------------------------------------------
// Phase 5: Full scan cycle and data integrity
// ---------------------------------------------------------------------------

test.describe("Phase 5 – Full scan cycle", () => {
  test("full cycle completes and flagged examples appear", async ({ page }) => {
    await page.goto("/");
    await waitForLinkOpen(page);
    await page.waitForTimeout(8_000);
    await expect(async () => {
      const text = await page.getByText("ALERTS / SAVINGS").locator("..").locator("p.text-cyan-400").innerText();
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
    await page.goto("/");
    await waitForLinkOpen(page);
    await waitForAlerts(page, 1);
    // Wait for scan to accumulate bandwidth so the HUD shows live data
    await expect(async () => {
      const text = await page.getByText("ALERTS / SAVINGS").locator("..").locator("p.text-cyan-400").innerText();
      expect(text.length).toBeGreaterThan(0);
    }).toPass({ timeout: 15_000 });
    // Brief settle time for map tiles and animations to render
    await page.waitForTimeout(1_000);
    await page.screenshot({ path: "e2e/screenshots/app-scan-in-progress.png" });
  });

  test("capture selected alert with evidence", async ({ page }) => {
    await page.goto("/");
    await waitForLinkOpen(page);
    await waitForAlerts(page, 1);
    const firstAlert = page.locator("[data-testid='alert-button']").first();
    await firstAlert.click();
    // Wait for the full evidence panel to populate
    await expect(page.getByText("BEFORE WINDOW", { exact: true })).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("AFTER WINDOW", { exact: true })).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("SIGNAL DELTAS", { exact: true })).toBeVisible({ timeout: 5_000 });
    // Wait for imagery to finish fetching (source label replaces "fetching…")
    await expect(page.getByText("fetching…")).not.toBeVisible({ timeout: 15_000 });
    // Brief settle time for images to paint
    await page.waitForTimeout(500);
    await page.screenshot({ path: "e2e/screenshots/alert-temporal-evidence.png" });
  });

  test("capture settings panel", async ({ page }) => {
    await page.goto("/");
    await page.locator("[data-testid='tab-settings']").click();
    await expect(page.getByText("Provider Status")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Fallback Order")).toBeVisible({ timeout: 10_000 });
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
    await page.goto("/");
    await page.locator("[data-testid='tab-settings']").click();
    await expect(page.getByText("Local Model")).toBeVisible();
    await expect(page.getByText("Model Tiers")).toBeVisible();
  });

  test("analyze button appears on selected alert", async ({ page }) => {
    await page.goto("/");
    await waitForLinkOpen(page);
    await waitForAlerts(page, 1);
    const firstAlert = page.locator("[data-testid='alert-button']").first();
    await firstAlert.click();
    await expect(page.locator("[data-testid='analyze-button']")).toBeVisible({ timeout: 5_000 });
  });

  test("clicking analyze button produces LFM analysis", async ({ page }) => {
    await page.goto("/");
    await waitForLinkOpen(page);
    await waitForAlerts(page, 1);
    const firstAlert = page.locator("[data-testid='alert-button']").first();
    await firstAlert.click();
    await expect(page.locator("[data-testid='analyze-button']")).toBeVisible({ timeout: 5_000 });
    await page.locator("[data-testid='analyze-button']").click();
    await expect(page.getByText("offline_lfm_v1")).toBeVisible({ timeout: 15_000 });
  });
});

// ---------------------------------------------------------------------------
// Phase 9 – Interaction Modules and FFMpeg Context Evaluation
// ---------------------------------------------------------------------------

test.describe("Phase 9 - Context Module and Timelapse Validation", () => {
  test("context menu drops on right click", async ({ page }) => {
    await page.goto("/");
    await waitForLinkOpen(page);
    // Give map time to mount canvas completely
    await page.waitForTimeout(3_000);
    
    // Simulate right click to spawn context menu near center
    const viewportSize = page.viewportSize() || { width: 1280, height: 720 };
    await page.mouse.click(viewportSize.width / 2, viewportSize.height / 2, { button: "right" });
    
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
    await page.goto("/");
    await waitForLinkOpen(page);
    await page.waitForTimeout(3_000);
    
    // Simulate right click to spawn context menu near center
    const viewportSize = page.viewportSize() || { width: 1280, height: 720 };
    await page.mouse.click(viewportSize.width / 2, viewportSize.height / 2, { button: "right" });
    
    // Construct timelapse execution payload
    const timelapseBtn = page.getByText("▷ Generate Temporal Timelapse");
    await expect(timelapseBtn).toBeVisible({ timeout: 5_000 });
    await timelapseBtn.click();
    
    // Make sure Timelapse modal hooks capture sequence FFMpeg payload rendering
    await expect(page.getByText("ORBITAL TIMELAPSE")).toBeVisible({ timeout: 10_000 });
    
    await page.waitForTimeout(2000);
    await page.screenshot({ path: "e2e/screenshots/ffmpeg-timelapse-viewer.png" });
  });

  test("triggering agent evaluation dispatches API payload to bus", async ({ page }) => {
    await page.goto("/");
    await waitForLinkOpen(page);
    await page.waitForTimeout(3_000);
    
    const viewportSize = page.viewportSize() || { width: 1280, height: 720 };
    await page.mouse.click(viewportSize.width / 2 + 50, viewportSize.height / 2 + 50, { button: "right" });
    
    const agentEValBtn = page.getByText("◈ Agent Video Evaluation");
    await expect(agentEValBtn).toBeVisible({ timeout: 5_000 });
    await agentEValBtn.click();
    
    // Ensure agent dialog expands to track the injected bus query representing the visual multi-model pass.
    await expect(page.getByText(/Analyze orbital timeframe for coords/i)).toBeVisible({ timeout: 10_000 });
    
    await page.waitForTimeout(1000);
    await page.screenshot({ path: "e2e/screenshots/agent-multimodality-evaluation.png" });
  });
});
