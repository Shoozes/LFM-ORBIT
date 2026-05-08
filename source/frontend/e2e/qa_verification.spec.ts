import { test, expect } from "@playwright/test";
import { gotoApp, resetRuntimeState, startMission } from "./runtime";
import { API_BASE } from "./testUrls";

function formatDateInput(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function recentDateRange(days: number) {
  const now = new Date();
  const end = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const start = new Date(end);
  start.setDate(start.getDate() - days);
  return { startDate: formatDateInput(start), endDate: formatDateInput(end) };
}

test.describe("QA Verification — Single Page Architecture", () => {
  test.beforeEach(async ({ page, request }) => {
    await resetRuntimeState(request);
    await gotoApp(page);
  });

  test("verify all major panels render correctly", async ({ page }) => {
    // 1. Mission tab
    await page.getByTestId("tab-mission").click();
    await expect(page.getByText("New Mission", { exact: true })).toBeVisible();
    await expect(page.getByTestId("mission-task-input")).toBeVisible();

    // 2. Agents tab
    await page.getByTestId("tab-agents").click();
    await expect(page.getByTestId("header-agent-bus")).toBeVisible();
    await expect(page.getByTestId("agent-role-strip")).toContainText("Satellite Pruner");
    await expect(page.getByTestId("agent-role-strip")).toContainText("Ground Validator");
    await expect(page.getByTestId("ground-agent-operator-playbook")).toContainText("Operator Playbook");
    await expect(page.getByPlaceholder("Inject manual command into agent bus…")).toBeVisible();
    await expect(page.getByPlaceholder("Request replay, mission pack, link action...")).toBeVisible();

    // 3. Logs tab
    await page.getByTestId("tab-logs").click();
    await expect(page.getByText("Alerts & Logs")).toBeVisible();

    // 4. Settings tab
    await page.getByTestId("tab-settings").click();
    await expect(page.getByText("Provider Status")).toBeVisible();
    await expect(page.getByPlaceholder("Sentinel Client ID")).toBeVisible();
  });

  test("verify empty and disabled states", async ({ page }) => {
    await page.getByTestId("tab-mission").click();
    const launchBtn = page.getByRole("button", { name: /Launch Mission|Mission Complete/i });
    await expect(launchBtn).toBeVisible();
    await expect(launchBtn).toBeDisabled();

    // Settings save should be disabled automatically
    await page.getByTestId("tab-settings").click();
    const saveSettingsBtn = page.getByRole("button", { name: /save credentials/i });
    await expect(saveSettingsBtn).toBeVisible();
    await expect(saveSettingsBtn).toBeDisabled();

    // Logs state may be empty on boot or already contain early downlinks
    await page.getByTestId("tab-logs").click();
    await expect(async () => {
      const emptyVisible = await page.getByText("No alerts downlinked yet.").isVisible().catch(() => false);
      const alertButtons = await page.locator("[data-testid='alert-button']").count();
      expect(emptyVisible || alertButtons > 0).toBeTruthy();
    }).toPass();
  });

  test("verify Mission Control text entry and Launch behavior", async ({ page }) => {
    await page.getByTestId("tab-mission").click();

    await page.getByTestId("mission-task-input").fill("Detect canopy loss");

    const launchBtn = page.getByRole("button", { name: /Launch Mission|Mission Complete/i });
    await expect(launchBtn).toBeEnabled();
  });

  test("verify Ground Agent message input", async ({ page }) => {
    // Navigate to Agents tab
    await page.getByTestId("tab-agents").click();

    const chatInput = page.getByTestId("ground-agent-chat-input");
    await chatInput.fill("Start scanning the northern sector");

    const sendBtn = page.locator('button:has-text("Send")');
    await sendBtn.click();

    // Expect the user message to be reflected instantly
    await expect(page.getByText("Start scanning the northern sector")).toBeVisible();
  });

  test("verify Ground Agent multiline mission planning workflow", async ({ page }) => {
    await page.getByTestId("tab-agents").click();

    const chatInput = page.getByTestId("ground-agent-chat-input");
    await chatInput.fill([
      "try looking for recent drought conditions and wildfires in florida",
      "return the safest mission attempt and final result",
    ].join("\n"));
    await expect(chatInput).toHaveValue(/wildfires in florida\nreturn the safest mission attempt/);
    await page.getByRole("button", { name: "Send" }).click();

    const proposal = page.getByTestId("ground-agent-proposal-card");
    await expect(page.getByText("Planning pass complete.")).toBeVisible({ timeout: 15_000 });
    await expect(proposal).toBeVisible({ timeout: 15_000 });
    await expect(proposal).toContainText("Florida Fire/Drought Readiness Watch");
    await expect(proposal).toContainText("curated_mission_pack_ready");
    await expect(proposal).toContainText("fireline");
  });

  test("verify Ground Agent plans a semantic construction timelapse over Davenport", async ({ page }) => {
    await page.getByTestId("tab-agents").click();

    const chatInput = page.getByTestId("ground-agent-chat-input");
    await chatInput.fill("show me a timelapse of new construction in the last 10 years of Davenport Florida");
    await page.getByRole("button", { name: "Send" }).click();

    const proposal = page.getByTestId("ground-agent-proposal-card");
    await expect(page.getByText("Planning pass complete.")).toBeVisible({ timeout: 15_000 });
    await expect(proposal).toBeVisible({ timeout: 15_000 });
    await expect(proposal).toContainText("Davenport, FL");
    await expect(proposal).toContainText("urban_expansion");
    await expect(proposal).toContainText("construction footprint");
    await expect(proposal).toContainText("local_registry");
    await expect(proposal).toContainText("Launch Plan");
  });

  test("verify Ground Agent reframes garbage patch timelapse as debris candidate mission", async ({ page }) => {
    await page.getByTestId("tab-agents").click();

    const chatInput = page.getByTestId("ground-agent-chat-input");
    await chatInput.fill("show me one of the biggest garbage patches in the ocean and make a timelapse for every month in the last 10 years to current");
    await page.getByRole("button", { name: "Send" }).click();

    const proposal = page.getByTestId("ground-agent-proposal-card");
    await expect(page.getByText("Planning pass complete.")).toBeVisible({ timeout: 15_000 });
    await expect(proposal).toBeVisible({ timeout: 15_000 });
    await expect(proposal).toContainText("North Pacific Debris Convergence Review Window");
    await expect(proposal).toContainText("plastic");
    await expect(proposal).toContainText("monthly");
    await expect(proposal).toContainText("coastal debris candidate");
    await expect(proposal).toContainText("Great Pacific Garbage Patch mass");

    await proposal.getByRole("button", { name: "Launch Plan" }).click();

    await expect(page.getByTestId("tab-mission")).toHaveClass(/border-zinc-900/, { timeout: 15_000 });
    await expect(page.getByText(/Active Mission #/)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("AREA MAPPED")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("map-area-bbox")).toContainText("-145.60, 34.40, -145.40, 34.60");
    await expect(page.getByTestId("mission-evidence-panel")).toHaveCount(0);
    await expect(page.getByTestId("open-evidence-tools")).toHaveCount(0);

    const missionStatus = page.locator('[data-testid="mission-progress-status"], [data-testid="mission-complete-summary"]').first();
    await expect(missionStatus).toBeVisible({ timeout: 30_000 });
    await expect(missionStatus).toContainText(/Starting scan|Scanning selected area|Mission Pass Complete/);
    await expect(missionStatus).toContainText(/plastic|mission targets/);
  });

  test("verify Ground Agent operator shortcuts navigate the app", async ({ page }) => {
    await page.getByTestId("tab-agents").click();

    await expect(page.getByTestId("ground-agent-nav-object_evidence")).toHaveCount(0);
    await expect(page.getByTestId("ground-agent-nav-proof")).toBeDisabled();
    await expect(page.getByTestId("ground-agent-nav-proof-tip")).toHaveAttribute("data-ui-tip", "Start or load a mission first.");

    await page.getByTestId("ground-agent-nav-logs").click();
    await expect(page.getByText("Alerts & Logs")).toBeVisible();

    await page.getByTestId("tab-agents").click();
    await page.getByTestId("ground-agent-nav-settings").click();
    await expect(page.getByText("Provider Status")).toBeVisible();

    await page.getByTestId("tab-agents").click();
    await page.getByTestId("ground-agent-nav-mission").click();
    await expect(page.getByText("New Mission", { exact: true })).toBeVisible();
  });

  test("verify Ground Agent is the first operator surface", async ({ page }) => {
    await expect(page.getByTestId("tab-agents")).toHaveClass(/border-zinc-900/);
    await expect(page.getByText("Ground Agent").first()).toBeVisible();
    await expect(page.getByTestId("ground-agent-operator-playbook")).toContainText("Task, replay, inspect.");
    await expect(page.getByTestId("ground-agent-suggestions-label")).toContainText("Suggested Prompts");
    await expect(page.getByTestId("ground-agent-suggestions-label")).toContainText("Ask only. Confirm before app changes.");
    await expect(page.getByRole("button", { name: "Load Spain Larouco wildfire proof replay" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Load Florida SR-26 wildfire proof replay" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Load critical minerals proof replay" })).toBeVisible();
    await expect(page.getByTestId("header-agent-bus")).toContainText("SAT/GND Dialogue Bus");
  });

  test("verify first suggested replay exposes scan, markers, and proof next steps", async ({ page }) => {
    await page.getByRole("button", { name: "Load Spain Larouco wildfire proof replay" }).click();

    const proposal = page.getByTestId("ground-agent-proposal-card");
    await expect(proposal).toBeVisible({ timeout: 15_000 });
    await expect(proposal).toContainText("spain_larouco_wildfire_replay");
    await proposal.getByRole("button", { name: "Run Replay" }).click();

    await expect(page.getByText("REPLAY ACTIVE: spain_larouco_wildfire_replay")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("tab-inspect")).toHaveClass(/border-zinc-900/, { timeout: 15_000 });
    await expect(page.getByTestId("inspect-result-next-actions")).toBeVisible();
    await expect(page.getByTestId("inspect-open-proof")).toBeEnabled();
    await expect(page.getByTestId("inspect-open-proof")).toHaveAttribute("data-proof-ready", "true");
    await expect(page.getByTestId("inspect-open-proof")).toHaveClass(/proof-action-glow/);
    await expect(page.getByTestId("map-scan-paused-hint")).toContainText("Cached replay restored", { timeout: 15_000 });

    await page.getByTestId("inspect-open-proof").click();
    await expect(page.getByTestId("proof-mode-panel")).toBeVisible({ timeout: 15_000 });
    const proofLayout = await page.evaluate(() => {
      const panel = document.querySelector("[data-testid='proof-mode-panel']");
      const main = panel?.querySelector("main");
      const sections = panel ? Array.from(panel.querySelectorAll("main > *")) : [];
      return {
        panelClientHeight: panel?.clientHeight ?? 0,
        panelScrollHeight: panel?.scrollHeight ?? 0,
        mainClientHeight: main?.clientHeight ?? 0,
        mainScrollHeight: main?.scrollHeight ?? 0,
        overflowingSections: sections.filter((section) => section.scrollHeight > section.clientHeight + 2).length,
      };
    });
    expect(proofLayout.panelScrollHeight).toBeLessThanOrEqual(proofLayout.panelClientHeight + 2);
    expect(proofLayout.mainScrollHeight).toBeLessThanOrEqual(proofLayout.mainClientHeight + 2);
    expect(proofLayout.overflowingSections).toBe(0);
    await page.getByRole("button", { name: "Close" }).click();

    await expect(page.getByTestId("map-pin-satellite")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("map-pin-ground")).toBeVisible({ timeout: 15_000 });
    await expect(async () => {
      const separation = await page.evaluate(() => {
        const sat = document.querySelector("[data-testid='map-pin-satellite']")?.getBoundingClientRect();
        const ground = document.querySelector("[data-testid='map-pin-ground']")?.getBoundingClientRect();
        if (!sat || !ground) return 0;
        return Math.hypot(
          (sat.left + sat.width / 2) - (ground.left + ground.width / 2),
          (sat.top + sat.height / 2) - (ground.top + ground.height / 2),
        );
      });
      expect(separation).toBeGreaterThan(20);
    }).toPass({ timeout: 10_000 });

    await page.getByTestId("tab-agents").click();
    await page.getByTestId("map-pin-ground").click();
    await expect(page.getByTestId("tab-inspect")).toHaveClass(/border-zinc-900/, { timeout: 10_000 });
    await expect(page.getByTestId("map-pin-tooltip")).toContainText("Ground marker", { timeout: 10_000 });
  });

  test("verify wide screens keep map and operator panels side by side", async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await gotoApp(page);

    await expect(page.getByTestId("app-map-pane")).toBeVisible();
    await expect(page.getByTestId("app-chat-pane")).toBeVisible();
    await expect(page.getByTestId("mobile-main-nav")).toBeHidden();
    await expect(page.getByTestId("header-agent-bus")).toContainText("SAT/GND Dialogue Bus");

    const layout = await page.evaluate(() => {
      const map = document.querySelector("[data-testid='app-map-pane']")?.getBoundingClientRect();
      const panel = document.querySelector("[data-testid='app-chat-pane']")?.getBoundingClientRect();
      return {
        bodyWidth: document.documentElement.clientWidth,
        scrollWidth: document.documentElement.scrollWidth,
        mapWidth: map?.width ?? 0,
        panelWidth: panel?.width ?? 0,
      };
    });
    expect(layout.scrollWidth).toBeLessThanOrEqual(layout.bodyWidth + 1);
    expect(layout.mapWidth).toBeGreaterThan(900);
    expect(layout.panelWidth).toBeGreaterThanOrEqual(500);
    expect(layout.panelWidth).toBeLessThanOrEqual(700);
  });

  test("verify 16:9 mobile shell uses Chat and Map as primary views", async ({ page }) => {
    await page.setViewportSize({ width: 640, height: 360 });
    await gotoApp(page);

    await expect(page.getByTestId("mobile-main-nav")).toBeVisible();
    await expect(page.getByTestId("mobile-nav-chat")).toBeVisible();
    await expect(page.getByTestId("mobile-nav-map")).toBeVisible();
    await expect(page.getByTestId("app-chat-pane")).toBeVisible();
    await expect(page.getByTestId("app-map-pane")).toBeHidden();
    await expect(page.getByTestId("ground-agent-operator-playbook")).toBeVisible();
    await expect(page.getByTestId("ground-agent-message-assistant").first()).toBeVisible();
    await expect(page.getByTestId("header-agent-bus")).toBeHidden();

    await page.getByTestId("mobile-nav-map").click();
    await expect(page.getByTestId("app-map-pane")).toBeVisible();
    await expect(page.getByTestId("app-chat-pane")).toBeHidden();
    await expect(page.getByTestId("map-area-tools")).toBeVisible();

    const mapLayout = await page.evaluate(() => ({
      bodyWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
      navBottom: document.querySelector("[data-testid='mobile-main-nav']")?.getBoundingClientRect().bottom ?? 0,
      viewportHeight: window.innerHeight,
    }));
    expect(mapLayout.scrollWidth).toBeLessThanOrEqual(mapLayout.bodyWidth + 1);
    expect(mapLayout.navBottom).toBeLessThanOrEqual(mapLayout.viewportHeight);

    await page.getByTestId("mobile-nav-chat").click();
    await expect(page.getByTestId("app-chat-pane")).toBeVisible();
    await expect(page.getByTestId("app-map-pane")).toBeHidden();
    await expect(page.getByRole("button", { name: "Load Spain Larouco wildfire proof replay" })).toBeVisible();
  });

  test("verify 9:16 mobile shell keeps Chat and Map usable", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await gotoApp(page);

    await expect(page.getByTestId("mobile-main-nav")).toBeVisible();
    await expect(page.getByTestId("app-chat-pane")).toBeVisible();
    await expect(page.getByTestId("app-map-pane")).toBeHidden();
    await expect(page.getByTestId("ground-agent-operator-playbook")).toBeVisible();
    await expect(page.getByTestId("ground-agent-message-assistant").first()).toBeVisible();
    await expect(page.getByTestId("ground-agent-chat-input")).toBeVisible();

    const chatLayout = await page.evaluate(() => ({
      bodyWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
      navBottom: document.querySelector("[data-testid='mobile-main-nav']")?.getBoundingClientRect().bottom ?? 0,
      inputBottom: document.querySelector("[data-testid='ground-agent-chat-input']")?.getBoundingClientRect().bottom ?? 0,
      viewportHeight: window.innerHeight,
    }));
    expect(chatLayout.scrollWidth).toBeLessThanOrEqual(chatLayout.bodyWidth + 1);
    expect(chatLayout.navBottom).toBeLessThanOrEqual(chatLayout.viewportHeight);
    expect(chatLayout.inputBottom).toBeLessThan(chatLayout.navBottom);

    await page.getByTestId("mobile-nav-map").click();
    await expect(page.getByTestId("app-map-pane")).toBeVisible();
    await expect(page.getByTestId("app-chat-pane")).toBeHidden();
    await expect(page.getByTestId("map-area-tools")).toBeVisible();
    await expect(page.getByRole("button", { name: "Open spatial options at map center" })).toBeVisible();

    const mapLayout = await page.evaluate(() => ({
      bodyWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
      navTop: document.querySelector("[data-testid='mobile-main-nav']")?.getBoundingClientRect().top ?? 0,
      actionsBottom: document.querySelector("button[title='Open spatial options at map center']")?.getBoundingClientRect().bottom ?? 0,
      actionsTop: document.querySelector("button[title='Open spatial options at map center']")?.getBoundingClientRect().top ?? 0,
      creditTop: document.querySelector("[data-testid='map-basemap-credit']")?.getBoundingClientRect().top ?? 0,
    }));
    expect(mapLayout.scrollWidth).toBeLessThanOrEqual(mapLayout.bodyWidth + 1);
    expect(mapLayout.actionsBottom).toBeLessThan(mapLayout.navTop);
    expect(mapLayout.actionsTop).toBeLessThan(mapLayout.creditTop);
  });

  test("verify clean startup stays idle until an operator mission", async ({ page, request }) => {
    await expect(page.getByText("No Mission")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Scan animation paused - selected area ready")).toBeVisible();
    await expect(page.getByTestId("map-area-tools")).toBeVisible();
    await expect(page.getByTestId("map-area-status")).toContainText("Selected");
    await expect(page.getByTestId("map-draw-area-button")).toBeVisible();
    await expect(page.getByTestId("map-clear-area-button")).toBeEnabled();

    const missionResponse = await request.get(`${API_BASE}/api/mission/current`);
    expect(missionResponse.ok()).toBeTruthy();
    expect((await missionResponse.json()).mission).toBeNull();

    await expect(async () => {
      const statsResponse = await request.get(`${API_BASE}/api/agent/bus/stats`);
      expect(statsResponse.ok()).toBeTruthy();
      const stats = await statsResponse.json() as { total_messages: number };
      expect(stats.total_messages).toBeLessThanOrEqual(3);
    }).toPass({ timeout: 10_000 });
  });

  test("verify Mission Control stays focused on plan and replay", async ({ page }) => {
    await page.getByTestId("tab-mission").click();
    await expect(page.getByTestId("mission-panel-tab-plan")).toHaveClass(/bg-white/);
    await expect(page.getByTestId("mission-preset-panel")).toBeVisible();
    await expect(page.getByTestId("fast-replay-panel")).not.toBeVisible();

    await page.getByTestId("mission-panel-tab-replay").click();
    await expect(page.getByTestId("fast-replay-panel")).toBeVisible();
    await expect(page.getByTestId("mission-preset-panel")).not.toBeVisible();
    await expect(page.getByTestId("mission-panel-tab-targets")).toHaveCount(0);
    await expect(page.getByTestId("mission-panel-tab-monitors")).toHaveCount(0);
  });

  test("verify Fire Watch presets use a recent operational date window", async ({ page }) => {
    await page.getByTestId("tab-mission").click();
    await page.getByTestId("mission-preset-fire_drought_florida_2026").click();

    const expected = recentDateRange(30);
    await expect(page.locator('input[type="date"]').nth(0)).toHaveValue(expected.startDate);
    await expect(page.locator('input[type="date"]').nth(1)).toHaveValue(expected.endDate);
  });

  test("verify Ground Agent can confirm a replay fetch action", async ({ page }) => {
    await page.getByTestId("tab-agents").click();

    const chatInput = page.getByPlaceholder("Request replay, mission pack, link action...");
    await chatInput.fill("replay a wildfire mission");
    await page.getByRole("button", { name: "Send" }).click();

    const proposal = page.getByTestId("ground-agent-proposal-card");
    await expect(proposal).toBeVisible({ timeout: 15_000 });
    await expect(proposal.getByText("Load replay: Highway 82 Wildfire Candidate Replay")).toBeVisible();
    await expect(proposal.getByText("georgia_wildfire_replay")).toBeVisible();
    await expect(proposal.getByText("cached_api")).toBeVisible();

    await proposal.getByRole("button", { name: "Run Replay" }).click();
    await expect(page.getByText("REPLAY ACTIVE: georgia_wildfire_replay")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("tab-inspect")).toHaveClass(/border-zinc-900/);

    await page.getByTestId("tab-mission").click();
    await expect(page.getByText("Replay Mission · georgia_wildfire_replay")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("REPLAY ACTIVE: georgia_wildfire_replay")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("mission-replay-open-first-result")).toBeEnabled();
    await expect(page.getByTestId("mission-replay-open-logs")).toBeVisible();
    await expect(page.getByTestId("mission-replay-open-proof")).toBeEnabled();
    await expect(page.getByTestId("mission-replay-open-proof")).toHaveAttribute("data-proof-ready", "true");
    await expect(page.getByTestId("mission-replay-open-proof")).toHaveClass(/proof-action-glow/);
    await page.getByTestId("mission-panel-tab-replay").click();
    await expect(page.getByTestId("rescan-replay-georgia_wildfire_replay")).toHaveText("Rescan Cache");
    await page.getByTestId("rescan-replay-georgia_wildfire_replay").click();
    await expect(page.getByTestId("tab-inspect")).toHaveClass(/border-zinc-900/, { timeout: 15_000 });
    await expect(page.getByText("REPLAY ACTIVE: georgia_wildfire_replay")).toBeVisible({ timeout: 15_000 });

    await page.getByTestId("tab-agents").click();
    await expect(page.getByTestId("ground-agent-nav-object_evidence")).toHaveCount(0);
    await expect(page.getByTestId("ground-agent-nav-proof")).toBeEnabled();
    await expect(page.getByTestId("ground-agent-nav-proof")).toHaveAttribute("data-proof-ready", "true");
    await expect(page.getByTestId("ground-agent-nav-proof-tip")).toHaveAttribute("data-ui-tip", "Proof is ready. Open results.");
    await page.getByTestId("ground-agent-nav-proof").click();
    await expect(page.getByTestId("proof-mode-panel")).toBeVisible({ timeout: 30_000 });
  });

  test("verify Ground Agent reframes protected wildlife population requests", async ({ page }) => {
    await page.getByTestId("tab-agents").click();

    const chatInput = page.getByPlaceholder("Request replay, mission pack, link action...");
    await chatInput.fill("try looking for manatee populations in florida");
    await page.getByRole("button", { name: "Send" }).click();

    const proposal = page.getByTestId("ground-agent-proposal-card");
    await expect(page.getByText("I cannot count or locate manatee populations from orbital imagery.")).toBeVisible({
      timeout: 15_000,
    });
    await expect(proposal).toBeVisible({ timeout: 15_000 });
    await expect(proposal).toContainText("Florida Manatee Habitat Review");
    await expect(proposal).toContainText("waterline");
  });

  test("verify Ground Agent handles hard manatee water searches as habitat proxy missions", async ({ page }) => {
    await page.getByTestId("tab-agents").click();

    const chatInput = page.getByTestId("ground-agent-chat-input");
    await chatInput.fill("try looking for manatees in water around Banana River in winter");
    await page.getByRole("button", { name: "Send" }).click();

    const proposal = page.getByTestId("ground-agent-proposal-card");
    await expect(page.getByText(/hard protected-wildlife mission/i)).toBeVisible({ timeout: 15_000 });
    await expect(proposal).toBeVisible({ timeout: 15_000 });
    await expect(proposal).toContainText("Banana River lagoon context");
    await expect(proposal).toContainText("protected wildlife habitat proxy ready");
    await expect(proposal).toContainText("waterline");
  });

  test("verify Ground Agent can stop mission state and fly map camera", async ({ page }) => {
    await page.getByTestId("tab-agents").click();

    const chatInput = page.getByPlaceholder("Request replay, mission pack, link action...");
    await chatInput.fill("cancel the current mission and take us to bull creek fl");
    await page.getByRole("button", { name: "Send" }).click();

    const proposal = page.getByTestId("ground-agent-proposal-card");
    await expect(proposal).toBeVisible({ timeout: 15_000 });
    await expect(proposal).toContainText("Bull Creek, FL");
    await expect(proposal).toContainText("Stop Mission");
    await expect(proposal).toContainText("wetland / pine-flatwoods context");
    await expect(proposal).toContainText("road or trail corridor");

    await proposal.getByRole("button", { name: "Stop & Fly Map" }).click();

    await expect(page.getByTestId("map-camera-hud")).toContainText("Bull Creek, FL", { timeout: 15_000 });
    await expect(page.getByTestId("map-camera-hud")).toContainText("wetland / pine-flatwoods context");
    await expect(page.getByTestId("map-camera-hud")).toContainText("Terrain:");
    await expect(page.getByTestId("map-camera-hud")).toContainText("canal or drainage line");
    await expect(page.getByTestId("mission-stopped-notice")).toContainText(/Mission Stopped|No active mission/i, {
      timeout: 15_000,
    });
    await expect(page.getByTestId("map-camera-hud")).toContainText("Arrived", { timeout: 15_000 });
    await expect(page.getByTestId("map-scan-paused-hint")).toBeVisible({ timeout: 15_000 });
  });

  test("verify Ground Agent can fly map camera to Bronx from chat", async ({ page }) => {
    await page.getByTestId("tab-agents").click();

    const chatInput = page.getByTestId("ground-agent-chat-input");
    await chatInput.fill("take me to the bronx, ny");
    await page.getByRole("button", { name: "Send" }).click();

    const proposal = page.getByTestId("ground-agent-proposal-card");
    await expect(proposal).toBeVisible({ timeout: 15_000 });
    await expect(proposal).toContainText("Bronx, NY");
    await expect(proposal).toContainText("urban borough context");
    await expect(proposal).toContainText("transport corridor");
    await expect(proposal.getByTestId("location-preview-tiles")).toBeVisible();
    await expect(proposal.getByText("local_registry")).toBeVisible();

    await proposal.getByRole("button", { name: "Fly Map" }).click();

    const hud = page.getByTestId("map-camera-hud");
    await expect(hud).toContainText("Bronx, NY", { timeout: 15_000 });
    await expect(hud).toContainText("urban borough context");
    await expect(hud).toContainText("Terrain:");
    await expect(hud).toContainText("shoreline or river boundary");
    await expect(hud).toContainText("Arrived", { timeout: 15_000 });
  });

  test("verify Ground Agent asks before redirecting active missions to map destinations", async ({ page, request }) => {
    await startMission(request, {
      task_text: "Run Florida Fire/Drought Readiness Watch over a North Florida corridor.",
      bbox: [-83.2, 29.0, -81.3, 30.7],
      start_date: "2026-04-15",
      end_date: "2026-04-25",
      use_case_id: "wildfire",
    });
    await page.getByTestId("tab-agents").click();

    const chatInput = page.getByTestId("ground-agent-chat-input");
    await chatInput.fill("take me to giza pyramid");
    await page.getByRole("button", { name: "Send" }).click();

    const proposal = page.getByTestId("ground-agent-proposal-card");
    await expect(page.getByText("You have an active mission. I can stop it and fly the camera to Giza Pyramid Complex")).toBeVisible({
      timeout: 15_000,
    });
    await expect(proposal).toBeVisible({ timeout: 15_000 });
    await expect(proposal).toContainText("Giza Pyramid Complex");
    await expect(proposal).toContainText("Stop Mission");
    await expect(proposal).toContainText("archaeological heritage site context");

    await proposal.getByRole("button", { name: "Stop & Fly Map" }).click();
    await expect(page.getByTestId("map-camera-hud")).toContainText("Giza Pyramid Complex", { timeout: 15_000 });
    await expect(page.getByTestId("map-camera-hud")).toContainText("archaeological heritage site context");
  });

  test("verify Ground Agent surfaces backend errors", async ({ page }) => {
    await page.route("**/api/agent/chat", async (route) => {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ error: "Mock assistant outage" }),
      });
    });

    await page.getByTestId("tab-agents").click();

    const chatInput = page.getByPlaceholder("Request replay, mission pack, link action...");
    await chatInput.fill("Start fallback analysis");
    await page.getByRole("button", { name: "Send" }).click();

    await expect(page.getByText("Start fallback analysis")).toBeVisible();
    await expect(page.getByText("[Link Error: Mock assistant outage]")).toBeVisible({ timeout: 10_000 });
  });

  test("verify Ground Agent proposal confirmation surfaces action errors", async ({ page }) => {
    await page.route("**/api/agent/action/confirm", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          reply: "Mock confirm rejected",
          actions: [
            {
              name: "set_link_state",
              status: "error",
              result: { error: "Mock confirm rejected" },
            },
          ],
          suggestions: ["List replays"],
        }),
      });
    });

    await page.getByTestId("tab-agents").click();
    await page.getByPlaceholder("Request replay, mission pack, link action...").fill("set link offline");
    await page.getByRole("button", { name: "Send" }).click();

    const proposal = page.getByTestId("ground-agent-proposal-card");
    await expect(proposal).toBeVisible({ timeout: 10_000 });
    await proposal.getByRole("button", { name: "Set Offline" }).click();

    await expect(proposal.getByText("Mock confirm rejected")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("set link state - Mock confirm rejected")).toBeVisible();
  });

  test("verify Agent Dialogue surfaces bus failures", async ({ page }) => {
    await page.route("**/api/agent/bus/stats", async (route) => {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ error: "Mock stats outage" }),
      });
    });
    await page.route("**/api/agent/bus/inject", async (route) => {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ error: "Mock bus outage" }),
      });
    });

    await page.getByTestId("tab-agents").click();
    await expect(page.getByText("Bus stats unavailable")).toBeVisible({ timeout: 10_000 });

    const injectInput = page.getByPlaceholder("Inject manual command into agent bus…");
    await injectInput.fill("Check sensor handoff");
    await page.getByRole("button", { name: "Inject" }).click();

    await expect(page.getByText("Mock bus outage")).toBeVisible({ timeout: 10_000 });
  });

  test("verify map UI elements load and LINK OPEN has tooltip", async ({ page }) => {
    // Expect Map element to be mounted
    await expect(page.locator(".maplibregl-map")).toBeVisible({ timeout: 10_000 });

    // Check that LINK OPEN or DISCONNECTED badge exists and has title
    const linkBadge = page.locator('div[title="Telemetry Link Status (View Only)"]');
    await expect(linkBadge).toBeVisible();
  });

  test("verify map-side Area Tools drawing and cancellation", async ({ page }) => {
    await expect(page.getByTestId("map-area-tools")).toBeVisible();
    await page.getByTestId("map-clear-area-button").click();
    await expect(page.getByTestId("map-area-status")).toContainText("No Area");

    const drawBtn = page.getByTestId("map-draw-area-button");
    await drawBtn.click();
    await expect(page.getByTestId("map-area-status")).toContainText("Drawing");

    // Banner should appear
    const banner = page.getByText("DRAWING MODE ACTIVE");
    await expect(banner).toBeVisible();

    // Press escape to cancel
    await page.keyboard.press("Escape");
    await expect(banner).toBeHidden();
    await expect(page.getByTestId("map-area-status")).toContainText("No Area");
  });
});
