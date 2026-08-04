import { expect, test } from "@playwright/test";

test("hosted manifest contracts reject unsafe package and model data without fetching a model", async ({ page }) => {
  await page.goto("/hosted");
  const result = await page.evaluate(async () => {
    const packagesModule = await import("/hosted/demoPackages.ts");
    const modelModule = await import("/hosted/hostedModel.ts");
    const stateModule = await import("/hosted/modelState.ts");
    const packagePayload = await fetch("/demo-packages/index.json").then((response) => response.json());
    const modelPayload = await fetch("/model-manifest.json").then((response) => response.json());
    let packageRejected = false;
    let modelRejected = false;
    try {
      packagesModule.validateDemoPackageIndex({
        schemaVersion: packagePayload.schemaVersion,
        packages: [{ ...packagePayload.packages[0], imageSrc: "https://example.invalid/remote.png" }],
      });
    } catch {
      packageRejected = true;
    }
    let traversalRejected = false;
    try {
      packagesModule.validateDemoPackageIndex({
        schemaVersion: packagePayload.schemaVersion,
        packages: [{ ...packagePayload.packages[0], imageSrc: "/demo-assets/../model-manifest.json" }],
      });
    } catch {
      traversalRejected = true;
    }
    let provenanceRejected = false;
    try {
      packagesModule.validateDemoPackageIndex({
        schemaVersion: packagePayload.schemaVersion,
        packages: [{
          ...packagePayload.packages[0],
          evidence: { ...packagePayload.packages[0].evidence, sourceAsset: "https://example.invalid/replay.json" },
        }],
      });
    } catch {
      provenanceRejected = true;
    }
    try {
      modelModule.validateHostedModelManifest({ ...modelPayload, bytes: 999_000_000 });
    } catch {
      modelRejected = true;
    }
    return {
      packageCount: packagesModule.validateDemoPackageIndex(packagePayload).length,
      packageSchemaVersion: packagePayload.schemaVersion,
      sourceReplayId: packagePayload.packages[0].evidence.sourceReplayId,
      revision: modelModule.validateHostedModelManifest(modelPayload).revision,
      generationCancelStatus: stateModule.statusAfterBrowserModelCancellation("generating", true),
      downloadCancelStatus: stateModule.statusAfterBrowserModelCancellation("loading", false),
      abortError: stateModule.isBrowserModelAbortError(new DOMException("cancelled", "AbortError")),
      ordinaryError: stateModule.isBrowserModelAbortError(new Error("failed")),
      packageRejected,
      traversalRejected,
      provenanceRejected,
      modelRejected,
    };
  });

  expect(result.packageCount).toBe(3);
  expect(result.packageSchemaVersion).toBe(2);
  expect(result.sourceReplayId).toBe("atacama_mining_replay");
  expect(result.revision).toMatch(/^[a-f0-9]{40}$/);
  expect(result.generationCancelStatus).toBe("ready");
  expect(result.downloadCancelStatus).toBe("idle");
  expect(result.abortError).toBe(true);
  expect(result.ordinaryError).toBe(false);
  expect(result.packageRejected).toBe(true);
  expect(result.traversalRejected).toBe(true);
  expect(result.provenanceRejected).toBe(true);
  expect(result.modelRejected).toBe(true);
});
