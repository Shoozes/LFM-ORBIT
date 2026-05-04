import { expect, test } from "@playwright/test";
import { openDemo, saveProofArtifacts } from "./demoHelpers";

test("provenance demo exposes source, bbox, model, prompt, and output JSON", async ({ page, request }, testInfo) => {
  await openDemo(page, request, "provenance");

  await expect(page.getByTestId("demo-title")).toContainText("Critical minerals provenance proof");
  await expect(page.getByTestId("proof-timelapse-video")).toHaveCount(0);
  await expect(page.getByAltText("Satellite mission frame")).toBeVisible();
  await expect(page.getByTestId("timelapse-integrity")).toContainText("raw image stays local");
  await expect(page.getByText("provider:", { exact: false })).toBeVisible();
  await expect(page.getByText("replay id: mining_expansion")).toBeVisible();
  await expect(page.getByText("capture time: 2025-12-15")).toBeVisible();
  await expect(page.getByText("prompt: Track evaporation pond regions", { exact: false })).toBeVisible();
  await expect(page.getByTestId("proof-json")).toContainText("\"bbox\"");
  await expect(page.getByTestId("proof-json")).toContainText("\"output_json\"");

  const proof = await saveProofArtifacts(page, "provenance", testInfo);
  expect(proof.demo).toBe("provenance");
  expect(proof.provider).toContain("Sentinel Hub Sentinel-2 L2A");
  expect(proof.replay_id).toBe("mining_expansion");
  expect(proof.bbox).toEqual([-69.115, -24.29, -69.035, -24.21]);
  expect(proof.result).toContain("critical minerals");
  expect(proof.prompt).toContain("evaporation pond regions");
  expect(proof.output_json.status).toBe("alert_ready");
});
