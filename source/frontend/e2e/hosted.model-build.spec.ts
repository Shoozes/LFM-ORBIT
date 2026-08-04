import { test } from "@playwright/test";
import { exerciseHostedModel } from "./hostedModelTest";

test.setTimeout(10 * 60_000);

test("hosted production build fetches and runs the model in-browser", async ({ page }) => {
  await exerciseHostedModel(page, "/");
});
