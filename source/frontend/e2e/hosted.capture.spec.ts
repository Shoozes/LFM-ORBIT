import { copyFile } from "node:fs/promises";
import { expect, test } from "@playwright/test";

test("capture hosted portfolio stills", async ({ page }) => {
  test.setTimeout(60_000);
  const video = page.video();
  await page.goto("/hosted");
  await expect(page.getByRole("heading", { name: /small model turns satellite change/i })).toBeVisible();
  await page.waitForTimeout(2_000);
  await page.screenshot({
    path: "../../docs/media/readme/readme-hosted-demo.png",
    fullPage: false,
  });

  await page.getByRole("button", { name: /Show lesson map/i }).click();
  await page.waitForTimeout(2_000);
  await page.getByRole("button", { name: /Fireline review packet/i }).click();
  await expect(page.getByRole("heading", { name: "Fireline review packet" })).toBeVisible();
  await page.locator("#evidence").evaluate((element) => element.scrollIntoView({ block: "start", inline: "nearest" }));
  await page.waitForTimeout(2_000);
  await page.screenshot({
    path: "../../docs/media/readme/readme-hosted-evidence.png",
    fullPage: false,
  });

  await page.locator("#chat").evaluate((element) => element.scrollIntoView({ block: "start", inline: "nearest" }));
  await page.waitForTimeout(2_000);
  if (video) {
    await page.close();
    const videoPath = await video.path();
    if (!videoPath) throw new Error("Hosted capture video handle did not expose a path.");
    await copyFile(videoPath, "../../docs/media/videos/hosted-demo.webm");
  }
});
