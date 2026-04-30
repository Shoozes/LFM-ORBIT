import { test, expect } from "@playwright/test";
import { gotoApp, openMapContextMenu, waitForBasemapReady, waitForLinkOpen } from "./runtime";

test.describe("Visual evidence tools E2E test", () => {
  test("mounts visual evidence panel, sets bbox via context menu, executes search", async ({ page }) => {
    await gotoApp(page);
    await waitForLinkOpen(page);
    await waitForBasemapReady(page);
    await page.getByTestId("tab-mission").click();
    await page.getByTestId("mission-preset-traffic_i4_disney").click();
    await expect(page.getByTestId("selected-mission-preset")).toContainText("I-4 interchange");
    await openMapContextMenu(page);
    await page.getByText("◫ Set Mission BBox Here").click();

    await page.getByTestId("tab-mission").click();
    await expect(page.getByText("Visual Evidence Tools")).toBeVisible();

    const gInput = page.getByPlaceholder("Find: homes, boats, possible flaring, dark smoke");
    await expect(gInput).toBeVisible({ timeout: 5_000 });
    await gInput.fill("Find road corridor");
    await gInput.press("Enter");

    await expect(
      page.getByText(/road|Find road corridor|No matches found\./i).first(),
    ).toBeVisible({ timeout: 15_000 });

    await page.getByTestId("vlm-target-boats").click();
    await expect(gInput).toHaveValue("Find boats");
    await expect(page.getByTestId("vlm-grounding-result").filter({ hasText: /boats/i })).toBeVisible({ timeout: 15_000 });

    const vqaInput = page.getByPlaceholder("What land cover is visible?");
    await vqaInput.fill("What land cover is visible?");
    await vqaInput.press("Enter");
    await expect(page.getByText(/road corridor|water bodies|managed vegetation|Unable to answer precisely|Unknown\./i).first()).toBeVisible({ timeout: 15_000 });

    await page.getByRole("button", { name: "Generate" }).click();
    await expect(
      page.getByText(/Florida road corridor|satellite view|developed land|Describe the scene/i).first(),
    ).toBeVisible({ timeout: 15_000 });

    await page.screenshot({ path: "e2e/screenshots/vlm-panel-results.png" });
  });
});
