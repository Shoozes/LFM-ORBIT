import { expect, test } from "@playwright/test";
import { openDemo, saveProofArtifacts } from "./demoHelpers";

function formatProofBytes(bytes: number) {
  if (bytes >= 1_000_000) {
    return `${(bytes / 1_000_000).toFixed(2)} MB`;
  }
  if (bytes >= 1_000) {
    return `${(bytes / 1_000).toFixed(2)} KB`;
  }
  return `${bytes} B`;
}

test("showcase records deterministic evidence proof", async ({ page, request }, testInfo) => {
  await openDemo(page, request, "showcase");
  const proofPayload = JSON.parse((await page.getByTestId("proof-json").textContent()) ?? "{}") as {
    raw_payload_bytes?: number;
    alert_payload_bytes?: number;
    payload_reduction_ratio?: number;
  };
  expect(proofPayload.raw_payload_bytes).toBe(1_840_000);
  expect(proofPayload.alert_payload_bytes).toBeGreaterThan(0);
  expect(proofPayload.alert_payload_bytes).toBeLessThan(3_000);
  expect(proofPayload.payload_reduction_ratio).toBeGreaterThan(700);

  await expect(page.getByTestId("demo-title")).toContainText("Critical minerals expansion proof");
  await expect(page.getByText("Critical Minerals Expansion Watch").first()).toBeVisible();
  await expect(page.getByTestId("satellite-frame")).toBeVisible();
  await expect(page.getByTestId("proof-timelapse-video")).toBeVisible();
  await expect(page.getByTestId("timelapse-integrity")).toContainText("contextual frames");
  await expect(page.getByTestId("proof-latency")).toContainText("842 ms");
  await expect(page.getByTestId("proof-source")).toContainText(/Replay \(Sentinel Hub Cache\)|Replay \(Cached API Imagery\)/i);
  await expect(page.getByTestId("proof-raw-bytes")).toContainText(formatProofBytes(proofPayload.raw_payload_bytes ?? 0));
  await expect(page.getByTestId("proof-alert-bytes")).toContainText(formatProofBytes(proofPayload.alert_payload_bytes ?? 0));
  await expect(page.getByTestId("proof-payload-accounting")).toContainText("compact downlink alert JSON only");
  await expect(page.getByTestId("proof-reduction-ratio")).toContainText(
    `${Math.round(proofPayload.payload_reduction_ratio ?? 0).toLocaleString("en-US")}x`,
  );

  const proof = await saveProofArtifacts(page, "showcase", testInfo);
  expect(proof.demo).toBe("showcase");
  expect(proof.replay_id).toBe("atacama_mining_replay");
  expect(proof.abstained).toBe(false);
  expect(proof.result).toContain("critical minerals");
  expect(proof.raw_payload_bytes).toBe(proofPayload.raw_payload_bytes);
  expect(proof.alert_payload_bytes).toBe(proofPayload.alert_payload_bytes);
  expect(proof.payload_accounting.alert_payload_basis).toBe("compact downlink alert JSON only");
  expect(proof.payload_accounting.excluded_from_alert_payload_bytes).toContain("proof wrapper");
  expect(proof.artifacts.evidence_frame).toBe("evidence-frame.png");
});
