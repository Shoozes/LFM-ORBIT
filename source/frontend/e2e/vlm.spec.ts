import { test, expect, type APIRequestContext } from "@playwright/test";
import { gotoApp, resetRuntimeState, waitForBasemapReady, waitForLinkOpen } from "./runtime";
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
