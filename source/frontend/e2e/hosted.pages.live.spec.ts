import { test } from "@playwright/test";
import { exerciseHostedModel } from "./hostedModelTest";

test("deployed Pages origin loads and reuses the hosted model locally", async ({ page }, testInfo) => {
  const first = await exerciseHostedModel(page, process.env.HOSTED_PAGES_URL!);
  await page.reload();
  const second = await exerciseHostedModel(page, process.env.HOSTED_PAGES_URL!);

  await testInfo.attach("hosted-pages-model-timings.json", {
    body: JSON.stringify({ first, second }, null, 2),
    contentType: "application/json",
  });
});
