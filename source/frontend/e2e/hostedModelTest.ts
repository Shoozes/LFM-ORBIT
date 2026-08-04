import { expect, type Page } from "@playwright/test";

export async function exerciseHostedModel(page: Page, route: string): Promise<void> {
  const forbiddenRequests: string[] = [];
  const modelRequests: string[] = [];

  page.on("request", (request) => {
    const url = request.url();
    if (/:8000\b|\/api(?:\/|$)|\/ws(?:\/|$)/.test(url)) forbiddenRequests.push(url);
    if (url.includes("huggingface.co/") && url.endsWith(".gguf")) modelRequests.push(url);
  });

  await page.goto(route);
  await page.getByRole("button", { name: /Fetch the small model/i }).click();
  await expect(page.locator(".hosted-model-status")).toHaveText("Model loaded locally in this browser", { timeout: 9 * 60_000 });
  await expect(page.getByRole("textbox", { name: "Ask Orbit Classroom" })).toBeEnabled();

  const question = page.getByRole("textbox", { name: "Ask Orbit Classroom" });
  await question.fill("In one short sentence, what is this saved evidence packet for?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.locator(".hosted-chat-line.hosted-chat-assistant").last()).toContainText(/\S/, { timeout: 90_000 });

  expect(forbiddenRequests).toEqual([]);
  expect(modelRequests.length).toBeGreaterThan(0);
}
