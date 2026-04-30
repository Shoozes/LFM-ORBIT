import { expect, test } from "@playwright/test";
import { openDemo, saveProofArtifacts } from "./demoHelpers";

test("orbital eclipse demo queues packets offline and flushes on restore", async ({ page, request }, testInfo) => {
  await openDemo(page, request, "eclipse");

  await expect(page.getByTestId("demo-title")).toContainText("Maritime orbital eclipse proof");
  await expect(page.getByTestId("proof-timelapse-video")).toHaveCount(0);
  await expect(page.getByAltText("Satellite mission frame")).toBeVisible();
  await expect(page.getByTestId("timelapse-integrity")).toContainText("compact JSON queue");
  await expect(page.getByTestId("orbital-eclipse-toggle")).toBeVisible();
  await page.getByTestId("orbital-eclipse-toggle").click();
  await expect(page.getByText("LINK OFFLINE").first()).toBeVisible();
  await expect(page.getByTestId("dtn-queue-count")).toContainText(/[3-4] queued/, { timeout: 5_000 });

  await page.getByTestId("orbital-eclipse-toggle").click();
  await expect(page.getByText("LINK RESTORED", { exact: false }).first()).toBeVisible();
  await expect(page.getByTestId("dtn-queue-count")).toContainText("0 queued");
  await expect(page.getByTestId("dtn-proof-summary")).toContainText("queue_source: agent_bus_unread_messages");
  await expect(page.getByTestId("dtn-proof-summary")).toContainText("flushed_alerts: 4");

  const proof = await saveProofArtifacts(page, "orbital-eclipse", testInfo);
  expect(proof.demo).toBe("orbital-eclipse");
  expect(proof.replay_id).toBe("maritime_activity");
  expect(proof.result).toContain("maritime");
  expect(proof.output_json.status).toBe("alert_ready");
  expect(proof.output_json.queue_source).toBe("agent_bus_unread_messages");
  expect(proof.output_json.link_state_before).toBe("offline");
  expect(proof.output_json.link_state_after).toBe("restored");
  expect(proof.output_json.queued_alerts_before_restore).toBe(4);
  expect(proof.output_json.flushed_alerts).toBe(4);
});
