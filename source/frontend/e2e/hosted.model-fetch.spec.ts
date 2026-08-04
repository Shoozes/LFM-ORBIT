import { test } from "@playwright/test";
import { exerciseHostedModel } from "./hostedModelTest";

test.setTimeout(10 * 60_000);

test("hosted model fetch stays browser-local", async ({ page }) => {
  await exerciseHostedModel(page, "/hosted");
});
