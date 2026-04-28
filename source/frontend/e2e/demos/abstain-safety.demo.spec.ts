import { expect, test } from "@playwright/test";
import { openDemo, saveProofArtifacts } from "./demoHelpers";

test("abstain safety demo shows low-confidence no-transmit behavior", async ({ page, request }, testInfo) => {
  await openDemo(page, request, "abstain");

  await expect(page.getByTestId("demo-title")).toContainText("Greenland abstain safety proof");
  await expect(page.getByTestId("proof-timelapse-video")).toHaveCount(0);
  await expect(page.getByAltText("Satellite mission frame")).toBeVisible();
  await expect(page.getByTestId("timelapse-integrity")).toContainText("no alert transmitted");
  await expect(page.getByText("status: abstained").first()).toBeVisible();
  await expect(page.getByText("reason: imagery stale/cloudy/insufficient").first()).toBeVisible();
  await expect(page.getByText("confidence: low").first()).toBeVisible();
  await expect(page.getByText("no alert transmitted").first()).toBeVisible();
  await expect(page.getByTestId("proof-alert-bytes")).toContainText("0 B");
  await expect(page.getByTestId("proof-reduction-ratio")).toContainText("No downlink");

  const proof = await saveProofArtifacts(page, "abstain-safety", testInfo);
  expect(proof.demo).toBe("abstain-safety");
  expect(proof.replay_id).toBe("ice_cap_growth");
  expect(proof.abstained).toBe(true);
  expect(proof.alert_payload_bytes).toBe(0);
  expect(proof.output_json.transmitted).toBe(false);
});
