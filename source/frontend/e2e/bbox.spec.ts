import { test, expect } from "@playwright/test";
import { gotoApp, openMapContextMenu, resetRuntimeState, waitForBasemapReady } from "./runtime";

test.describe("Bounding Box Draw Validation", () => {
  test("map area tools expose selection status and clearing without opening Mission", async ({ page, request }) => {
    await resetRuntimeState(request);
    await gotoApp(page);
    await waitForBasemapReady(page);

    await expect(page.getByTestId("map-area-tools")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId("map-area-status")).toContainText("Selected");
    await expect(page.getByTestId("map-clear-area-button")).toBeEnabled();

    await page.getByTestId("map-clear-area-button").click();
    await expect(page.getByTestId("map-area-status")).toContainText("No Area");
    await expect(page.getByTestId("map-area-bbox")).toContainText("No selected area");
    await expect(page.getByTestId("map-clear-area-button")).toBeDisabled();

    await page.getByTestId("map-draw-area-button").click();
    await expect(page.getByTestId("map-area-status")).toContainText("Drawing");
    await expect(page.getByText("DRAWING MODE ACTIVE")).toBeVisible();

    await page.getByTestId("map-draw-area-button").click();
    await expect(page.getByTestId("map-area-status")).toContainText("No Area");
    await expect(page.getByText("DRAWING MODE ACTIVE")).toHaveCount(0);
  });

  test("drag-drawing a bbox updates Area Tools and the mission grid", async ({ page, request }) => {
    await resetRuntimeState(request);
    await gotoApp(page);
    await waitForBasemapReady(page);

    await page.getByTestId("map-clear-area-button").click();
    await expect(page.getByTestId("map-area-status")).toContainText("No Area");

    const canvas = page.locator(".maplibregl-canvas").first();
    await expect(canvas).toBeVisible({ timeout: 10_000 });
    const box = await canvas.boundingBox();
    expect(box).not.toBeNull();

    await page.getByTestId("map-draw-area-button").click();
    await expect(page.getByTestId("map-area-status")).toContainText("Drawing");
    await expect(page.getByText("DRAWING MODE ACTIVE")).toBeVisible();

    await page.mouse.move(box!.x + box!.width * 0.34, box!.y + box!.height * 0.34);
    await page.mouse.down();
    await page.mouse.move(box!.x + box!.width * 0.57, box!.y + box!.height * 0.58, { steps: 8 });
    await page.mouse.up();

    await expect(page.getByTestId("map-area-status")).toContainText("Selected");
    await expect(page.getByTestId("map-area-bbox")).not.toContainText("No selected area");
    await expect(page.getByTestId("map-area-tools")).toContainText(/\d+ cells/);
    await expect(page.getByText("DRAWING MODE ACTIVE")).toHaveCount(0);

    await page.getByTestId("tab-mission").click();
    await expect(page.getByText("Active Area")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId("view-timelapse-preview")).toBeVisible();
  });

  test("assigning a bbox from the map populates mission focus controls", async ({ page }) => {
    await gotoApp(page);

    await waitForBasemapReady(page);
    await openMapContextMenu(page);
    await expect(page.getByText("Spatial Options")).toBeVisible({ timeout: 5_000 });
    await page.getByText("◫ Set Mission BBox Here").click();

    await expect(page.getByTestId("view-timelapse-preview")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(/\[-?\d+\.\d+, -?\d+\.\d+, -?\d+\.\d+, -?\d+\.\d+\]/)).toBeVisible();
  });

  test("map actions button opens spatial options without right click", async ({ page }) => {
    await gotoApp(page);
    await waitForBasemapReady(page);

    const mapActionsButton = page.getByRole("button", { name: "Open spatial options at map center" });
    await expect(mapActionsButton).toBeEnabled({ timeout: 10_000 });
    await mapActionsButton.click();
    await expect(page.getByText("Spatial Options")).toBeVisible({ timeout: 5_000 });

    await page.keyboard.press("Escape");
    await expect(page.getByText("Spatial Options")).toBeHidden();

    await mapActionsButton.click();
    await page.getByText("◫ Set Mission BBox Here").click();

    await expect(page.getByTestId("view-timelapse-preview")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId("map-area-status")).toContainText("Selected");
  });

  test("mission form shows date validation errors before deployment", async ({ page, request }) => {
    await resetRuntimeState(request);
    await gotoApp(page);
    await page.locator("[data-testid='tab-mission']").click();

    await page.getByTestId("mission-task-input").fill("Detect temporal edge case validation.");
    await page.locator('input[type="date"]').first().fill("2025-06-01");
    await page.locator('input[type="date"]').nth(1).fill("2024-06-01");
    await page.getByRole("button", { name: "Launch Mission" }).click();

    await expect(page.getByText("Start date must be on or before end date.")).toBeVisible();
  });

  test("mission launch readiness explains missing task and optional area", async ({ page, request }) => {
    await resetRuntimeState(request);
    await gotoApp(page);
    await page.getByTestId("map-clear-area-button").click();
    await page.locator("[data-testid='tab-mission']").click();

    await expect(page.getByTestId("mission-launch-readiness")).toContainText("Add an instruction to launch.");
    await page.getByTestId("mission-task-input").fill("Review the active region for publish QA.");
    await expect(page.getByTestId("mission-launch-readiness")).toContainText("active region will be scanned");

    await openMapContextMenu(page);
    await page.getByText("◫ Set Mission BBox Here").click();
    await expect(page.getByTestId("mission-launch-readiness")).toContainText("selected area will be scanned");
  });
});
