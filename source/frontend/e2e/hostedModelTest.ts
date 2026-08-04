import { expect, type Page, type Request } from "@playwright/test";

export type HostedModelRunTiming = {
  modelRequests: number;
  modelReadyMs: number;
  generationMs: number;
  modelTransferBytes: number;
  modelFromDiskCache: boolean;
  modelFromServiceWorker: boolean;
  modelFromPrefetchCache: boolean;
  totalMs: number;
};

export async function exerciseHostedModel(page: Page, route: string): Promise<HostedModelRunTiming> {
  const forbiddenRequests: string[] = [];
  const modelResponses = new Map<string, { bytes: number; fromDiskCache: boolean; fromServiceWorker: boolean; fromPrefetchCache: boolean }>();
  const startedAt = Date.now();
  const client = await page.context().newCDPSession(page);

  const onPageRequest = (request: Request) => {
    const url = request.url();
    if (/:8000\b|\/api(?:\/|$)|\/ws(?:\/|$)/.test(url)) forbiddenRequests.push(url);
  };
  const onResponseReceived = (event: {
    requestId: string;
    response: { url: string; fromDiskCache?: boolean; fromServiceWorker?: boolean; fromPrefetchCache?: boolean };
  }) => {
    if (!/\.gguf(?:[?#]|$)/i.test(event.response.url)) return;
    modelResponses.set(event.requestId, {
      bytes: 0,
      fromDiskCache: event.response.fromDiskCache === true,
      fromServiceWorker: event.response.fromServiceWorker === true,
      fromPrefetchCache: event.response.fromPrefetchCache === true,
    });
  };
  const onLoadingFinished = (event: { requestId: string; encodedDataLength?: number }) => {
    const response = modelResponses.get(event.requestId);
    if (response) response.bytes = Math.max(0, Math.round(event.encodedDataLength ?? 0));
  };

  page.on("request", onPageRequest);
  client.on("Network.responseReceived", onResponseReceived);
  client.on("Network.loadingFinished", onLoadingFinished);
  try {
    await client.send("Network.enable");
    await page.goto(route);
    await page.getByRole("button", { name: /Fetch the small model/i }).click();
    await expect(page.locator(".hosted-model-status")).toHaveText("Model loaded locally in this browser", { timeout: 9 * 60_000 });
    const modelReadyMs = Date.now() - startedAt;
    await expect(page.getByRole("textbox", { name: "Ask Orbit Classroom" })).toBeEnabled();

    const question = page.getByRole("textbox", { name: "Ask Orbit Classroom" });
    await question.fill("In one short sentence, what is this saved evidence packet for?");
    const generationStartedAt = Date.now();
    await page.getByRole("button", { name: "Ask", exact: true }).click();
    await expect(page.locator(".hosted-chat-line.hosted-chat-assistant").last()).toContainText(/\S/, { timeout: 90_000 });
    const generationMs = Date.now() - generationStartedAt;
    const modelRecords = [...modelResponses.values()];

    expect(forbiddenRequests).toEqual([]);
    expect(modelRecords.length).toBeGreaterThan(0);
    return {
      modelRequests: modelRecords.length,
      modelReadyMs,
      generationMs,
      modelTransferBytes: modelRecords.reduce((total, record) => total + record.bytes, 0),
      modelFromDiskCache: modelRecords.some((record) => record.fromDiskCache),
      modelFromServiceWorker: modelRecords.some((record) => record.fromServiceWorker),
      modelFromPrefetchCache: modelRecords.some((record) => record.fromPrefetchCache),
      totalMs: Date.now() - startedAt,
    };
  } finally {
    page.off("request", onPageRequest);
    client.off("Network.responseReceived", onResponseReceived);
    client.off("Network.loadingFinished", onLoadingFinished);
    await client.detach().catch(() => undefined);
  }
}
