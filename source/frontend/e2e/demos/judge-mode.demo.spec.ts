import { expect, test } from "@playwright/test";
import { openDemo, saveProofArtifacts } from "./demoHelpers";

test("judge mode records deterministic evidence proof", async ({ page, request }, testInfo) => {
  await openDemo(page, request, "judge");

  await expect(page.getByTestId("demo-title")).toContainText("Judge walkthrough proof");
  await expect(page.getByTestId("satellite-frame")).toBeVisible();
  await expect(page.getByTestId("proof-timelapse-video")).toBeVisible();
  await expect(page.getByTestId("timelapse-integrity")).toContainText("25 contextual frames");
  await expect(page.getByTestId("proof-latency")).toContainText("842 ms");
  await expect(page.getByTestId("proof-source")).toContainText(/Replay \(Sentinel Hub Cache\)|Replay \(Cached API Imagery\)/i);
  await expect(page.getByTestId("proof-raw-bytes")).toContainText("1.84 MB");
  await expect(page.getByTestId("proof-alert-bytes")).toContainText("1.24 KB");
  await expect(page.getByTestId("proof-payload-accounting")).toContainText("compact downlink alert JSON only");
  await expect(page.getByTestId("proof-reduction-ratio")).toContainText("1,483x");

  const proof = await saveProofArtifacts(page, "judge-mode", testInfo);
  expect(proof.demo).toBe("judge-mode");
  expect(proof.replay_id).toBe("rondonia_frontier_judge");
  expect(proof.abstained).toBe(false);
  expect(proof.result).toContain("forest boundary disturbance");
  expect(proof.raw_payload_bytes).toBe(1_840_000);
  expect(proof.alert_payload_bytes).toBe(1_240);
  expect(proof.payload_accounting.alert_payload_basis).toBe("compact downlink alert JSON only");
  expect(proof.payload_accounting.excluded_from_alert_payload_bytes).toContain("proof wrapper");
  expect(proof.artifacts.evidence_frame).toBe("evidence-frame.png");
});
