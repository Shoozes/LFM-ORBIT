import { expect, type APIRequestContext, type Page } from "@playwright/test";
import { API_BASE } from "./testUrls";

export async function gotoApp(page: Page, path = "/") {
  let lastError: unknown;
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    try {
      await page.goto(path, { waitUntil: "load" });
      return;
    } catch (error) {
      lastError = error;
      if (attempt === 3) {
        throw error;
      }
      await page.waitForTimeout(500 * attempt);
    }
  }

  throw lastError;
}

export async function resetRuntimeState(
  request: APIRequestContext,
  options?: { clearObservationStoreFiles?: boolean },
) {
  let lastError: unknown;
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    try {
      const response = await request.post(`${API_BASE}/api/runtime/reset`, {
        data: {
          clear_observation_store_files: options?.clearObservationStoreFiles ?? false,
        },
      });
      expect(response.ok()).toBeTruthy();
      return response.json();
    } catch (error) {
      lastError = error;
      if (attempt === 3) {
        throw error;
      }
      await new Promise((resolve) => setTimeout(resolve, 350));
    }
  }

  throw lastError;
}

export async function loadSeededReplay(request: APIRequestContext, replayId = "rondonia_frontier_judge") {
  const response = await request.post(`${API_BASE}/api/replay/load/${replayId}`);
  expect(response.ok()).toBeTruthy();
  return response.json();
}

export async function waitForLinkOpen(page: Page, timeoutMs = 30_000) {
  await expect(page.getByText("LINK OPEN")).toBeVisible({ timeout: timeoutMs });
}

export async function waitForBasemapReady(page: Page, timeoutMs = 20_000) {
  await expect(page.getByText(/Esri World Imagery/)).toBeVisible({ timeout: timeoutMs });
  await page.waitForTimeout(750);
}

export async function openMapContextMenu(
  page: Page,
  options?: { xRatio?: number; yRatio?: number },
) {
  const canvas = page.locator(".maplibregl-canvas").first();
  await expect(canvas).toBeVisible({ timeout: 15_000 });
  const box = await canvas.boundingBox();
  expect(box).not.toBeNull();

  const menu = page.getByText("Spatial Options");
  const candidates = [
    [options?.xRatio ?? 0.28, options?.yRatio ?? 0.42],
    [0.72, 0.58],
    [0.46, 0.76],
  ];

  for (const [xRatio, yRatio] of candidates) {
    await page.mouse.click(
      box!.x + box!.width * xRatio,
      box!.y + box!.height * yRatio,
      { button: "right" },
    );
    try {
      await expect(menu).toBeVisible({ timeout: 1_500 });
      return;
    } catch {
      await page.keyboard.press("Escape").catch(() => {});
    }
  }

  const actionsButton = page.getByTestId("map-actions-button");
  await expect(actionsButton).toBeEnabled({ timeout: 5_000 });
  await actionsButton.click();
  await expect(menu).toBeVisible({ timeout: 5_000 });
}
