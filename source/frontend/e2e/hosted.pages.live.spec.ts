import { expect, test } from "@playwright/test";
import { exerciseHostedModel } from "./hostedModelTest";

test("deployed Pages origin loads and reuses the hosted model locally", async ({ page }, testInfo) => {
  const first = await exerciseHostedModel(page, process.env.HOSTED_PAGES_URL!);
  const second = await exerciseHostedModel(page, process.env.HOSTED_PAGES_URL!);

  expect(first.modelTransferBytes).toBeGreaterThan(0);
  expect(
    second.modelFromDiskCache
      || second.modelFromServiceWorker
      || second.modelFromPrefetchCache
      || second.modelTransferBytes < first.modelTransferBytes,
  ).toBe(true);

  await testInfo.attach("hosted-pages-model-timings.json", {
    body: JSON.stringify({ first, second }, null, 2),
    contentType: "application/json",
  });
});
