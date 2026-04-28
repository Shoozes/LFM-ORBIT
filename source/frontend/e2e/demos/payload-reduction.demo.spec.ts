import { expect, test } from "@playwright/test";
import { openDemo, saveProofArtifacts } from "./demoHelpers";

test("payload demo shows raw frame to compact alert reduction", async ({ page, request }, testInfo) => {
  await openDemo(page, request, "payload");

  await expect(page.getByTestId("demo-title")).toContainText("Pakistan flood payload reduction proof");
  await expect(page.getByTestId("proof-timelapse-video")).toHaveCount(0);
  await expect(page.getByAltText("Satellite mission frame")).toBeVisible();
  await expect(page.getByTestId("timelapse-integrity")).toContainText("raw image stays local");
  await expect(page.getByTestId("proof-raw-bytes")).toContainText("Raw frame: 1.84 MB");
  await expect(page.getByTestId("proof-alert-bytes")).toContainText("Alert JSON: 1.24 KB");
  await expect(page.getByText("Downlink reduction: 1,483x").first()).toBeVisible();
  await expect(page.getByTestId("proof-reduction-ratio")).toContainText("1,483x");

  const proof = await saveProofArtifacts(page, "payload-reduction", testInfo);
  expect(proof.demo).toBe("payload-reduction");
  expect(proof.replay_id).toBe("flood_extent");
  expect(proof.result).toContain("Manchar Lake flood");
  expect(proof.bbox).toEqual([67.63, 26.31, 67.87, 26.55]);
  expect(proof.payload_reduction_ratio).toBeCloseTo(1483.87, 2);
  expect(proof.alert_payload_bytes).toBe(1_240);
});
