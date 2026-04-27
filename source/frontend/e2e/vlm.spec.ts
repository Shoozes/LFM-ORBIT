import { test, expect } from "@playwright/test";
import { gotoApp, openMapContextMenu, waitForBasemapReady, waitForLinkOpen } from "./runtime";

test.describe("VLM Grounds E2E visual test", () => {
  test("mounts VLM panel, sets bbox via context menu, executes search", async ({ page }) => {
    await gotoApp(page);
    await waitForLinkOpen(page);
    await waitForBasemapReady(page);
    await openMapContextMenu(page);
    await page.getByText("◫ Set Mission BBox Here").click();

    await page.getByTestId("tab-mission").click();
    await expect(page.getByText("VLM Vision")).toBeVisible();

    const gInput = page.getByPlaceholder("Find: large airplane (lower-left)");
    await expect(gInput).toBeVisible({ timeout: 5_000 });
    await gInput.fill("Find airplanes");
    await gInput.press("Enter");

    await expect(
      page.getByText(/airplane|Find airplanes|No matches found\./i).first(),
    ).toBeVisible({ timeout: 15_000 });

    const vqaInput = page.getByPlaceholder("How many large planes are visible?");
    await vqaInput.fill("How many airplanes");
    await vqaInput.press("Enter");
    await expect(page.getByText(/3\.|Unable to answer precisely|Unknown\./i).first()).toBeVisible({ timeout: 15_000 });

    await page.getByRole("button", { name: "Generate" }).click();
    await expect(
      page.getByText(/Deforested clearing|satellite view|intact canopy|Describe the scene/i).first(),
    ).toBeVisible({ timeout: 15_000 });

    await page.screenshot({ path: "e2e/screenshots/vlm-panel-results.png" });
  });
});
