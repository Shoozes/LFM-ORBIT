import { expect, test, type Page } from "@playwright/test";
import { gotoApp, loadSeededReplay, resetRuntimeState, waitForLinkOpen } from "./runtime";

const REVIEW_IMAGE_B64 =
  "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFElEQVR42mNk+M9Qz0AEYBxVSFUBAD2tBAbnh5jcAAAAAElFTkSuQmCC";

async function routeReviewImage(page: Page) {
  await page.route("**/api/gallery/*/visual-review-image", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        available: true,
        image_b64: REVIEW_IMAGE_B64,
        frame_id: "after_window_2025-01-15",
        source: "cached_api",
        runtime_truth_mode: "replay",
        imagery_origin: "cached_api",
        scoring_basis: "proxy_bands",
        bbox: [-63.05, -10.05, -62.95, -9.95],
      }),
    });
  });
}

async function routeProofSidecars(page: Page) {
  await page.route("**/api/vlm/grounding", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        results: [{ label: "retained evidence frame", bbox: [-63.05, -10.05, -62.95, -9.95] }],
      }),
    });
  });
  await page.route("**/api/vlm/vqa", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ answer: "Retained evidence frame is ready for visual review." }),
    });
  });
  await page.route("**/api/vlm/caption", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ caption: "Retained replay evidence with source-backed context." }),
    });
  });
}

async function openProofMode(page: Page) {
  await gotoApp(page);
  await waitForLinkOpen(page);
  await expect(page.getByTestId("ground-agent-nav-proof")).toBeEnabled({ timeout: 10_000 });
  const imageReviewResponse = page.waitForResponse(
    (response) => response.url().includes("/api/inference/image") && response.request().method() === "POST",
    { timeout: 30_000 },
  );
  await page.getByTestId("ground-agent-nav-proof").click();
  await expect(page.getByTestId("proof-mode-panel")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("proof-image-conditioned-review")).toBeVisible({ timeout: 30_000 });
  await imageReviewResponse;
}

test.describe("Proof Mode image-conditioned review", () => {
  test("renders successful retained-frame review in the proof JSON", async ({ page, request }) => {
    await resetRuntimeState(request);
    await loadSeededReplay(request, "atacama_mining_replay");
    await routeReviewImage(page);
    await routeProofSidecars(page);
    await page.route("**/api/inference/image", async (route) => {
      const body = route.request().postDataJSON() as Record<string, unknown>;
      expect(body.image_path).toBeUndefined();
      expect(String(body.image_b64 || "")).toContain("data:image/png;base64,");
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          available: true,
          image_conditioned: true,
          abstained: false,
          runtime_backend: "transformers_vlm",
          runtime_inference_mode: "image_conditioned_review",
          visual_model: "LiquidAI/LFM2.5-VL-450M",
          response: "Visible exposed soil expands around the retained mine-edge frame.",
          reason: "ok",
          provenance: {
            image_conditioned: true,
            visual_model: "LiquidAI/LFM2.5-VL-450M",
            image_source: "cached_api",
            frame_id: "after_window_2025-01-15",
            runtime_truth_mode: "replay",
            imagery_origin: "cached_api",
            scoring_basis: "proxy_bands",
            bbox: [-63.05, -10.05, -62.95, -9.95],
          },
        }),
      });
    });

    await openProofMode(page);

    await expect(page.getByTestId("proof-image-conditioned-review")).toContainText("Image-conditioned review");
    await expect(page.getByTestId("proof-image-conditioned-review")).toContainText("LiquidAI/LFM2.5-VL-450M");
    await expect(page.getByTestId("proof-image-conditioned-review")).toContainText("Visible exposed soil");
    await expect(page.getByTestId("proof-json")).toContainText('"visual_model_review"');
    await expect(page.getByTestId("proof-json")).toContainText('"image_conditioned": true');
    await expect(page.getByTestId("proof-json")).toContainText('"frame_id": "after_window_2025-01-15"');
  });

  test("renders unavailable review without inventing visual evidence", async ({ page, request }) => {
    await resetRuntimeState(request);
    await loadSeededReplay(request, "atacama_mining_replay");
    await routeReviewImage(page);
    await routeProofSidecars(page);
    await page.route("**/api/inference/image", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          available: false,
          image_conditioned: false,
          abstained: false,
          runtime_backend: "transformers_vlm",
          runtime_inference_mode: "text_evidence_packet",
          visual_model: "LiquidAI/LFM2.5-VL-450M",
          response: "",
          reason: "transformers_vlm image adapter has not been loaded yet",
          provenance: {
            image_conditioned: false,
            frame_id: "after_window_2025-01-15",
            runtime_truth_mode: "replay",
            imagery_origin: "cached_api",
          },
        }),
      });
    });

    await openProofMode(page);

    await expect(page.getByTestId("proof-image-conditioned-review")).toContainText("Image-conditioned review unavailable");
    await expect(page.getByTestId("proof-image-conditioned-review")).toContainText("has not been loaded yet");
    await expect(page.getByTestId("proof-json")).toContainText('"status": "unavailable"');
    await expect(page.getByTestId("proof-json")).not.toContainText('"image_conditioned": true');
  });

  test("renders abstain state for low-information retained frames", async ({ page, request }) => {
    await resetRuntimeState(request);
    await loadSeededReplay(request, "atacama_mining_replay");
    await routeReviewImage(page);
    await routeProofSidecars(page);
    await page.route("**/api/inference/image", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          available: true,
          image_conditioned: false,
          abstained: true,
          runtime_backend: "transformers_vlm",
          runtime_inference_mode: "image_conditioned_review",
          visual_model: "LiquidAI/LFM2.5-VL-450M",
          response: "No visible evidence was reviewed because the selected image chip is blank or no-data.",
          reason: "blank_or_no_data_image",
          provenance: {
            image_conditioned: false,
            visual_model: "LiquidAI/LFM2.5-VL-450M",
            image_source: "cached_api",
            frame_id: "after_window_2025-01-15",
            runtime_truth_mode: "replay",
            imagery_origin: "cached_api",
            scoring_basis: "proxy_bands",
          },
        }),
      });
    });

    await openProofMode(page);

    await expect(page.getByTestId("proof-image-conditioned-review")).toContainText("Image-conditioned review abstained");
    await expect(page.getByTestId("proof-image-conditioned-review")).toContainText("blank or no-data");
    await expect(page.getByTestId("proof-json")).toContainText('"status": "abstained"');
    await expect(page.getByTestId("proof-json")).toContainText('"abstained": true');
  });
});
