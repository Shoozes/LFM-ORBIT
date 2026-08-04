import { expect, test } from "@playwright/test";

const hostedPagesUrl = process.env.HOSTED_PAGES_URL;
if (!hostedPagesUrl) {
  throw new Error("HOSTED_PAGES_URL is required for the deployed Pages static smoke test");
}

const forbiddenRuntimeRequest = /(?:^|\/)(?:api|ws)(?:\/|$)|:8000(?:\/|$)|huggingface\.co/i;

function contentType(response: { headers(): Record<string, string> }): string {
  return response.headers()["content-type"] ?? "";
}

function assetUrl(relativeOrAbsolutePath: string, pageUrl: string): string {
  return new URL(relativeOrAbsolutePath, pageUrl).toString();
}

function assetPathsFromHtml(html: string, extension: "js" | "css"): string[] {
  const paths = new Set<string>();
  const expression = new RegExp(`(?:src|href)=["']([^"']+\\.${extension}(?:\\?[^"']*)?)["']`, "gi");
  for (const match of html.matchAll(expression)) {
    if (match[1]) paths.add(match[1]);
  }
  return [...paths];
}

function wasmPathsFromJavaScript(source: string): string[] {
  const paths = new Set<string>();
  const expression = /["'`]([^"'`\\]+\.wasm(?:\?[^"'`]*)?)["'`]/gi;
  for (const match of source.matchAll(expression)) {
    if (match[1]) paths.add(match[1]);
  }
  return [...paths];
}

function javascriptModulePaths(source: string): string[] {
  const paths = new Set<string>();
  const expressions = [
    /import\(\s*["'`]([^"'`\\]+\.js(?:\?[^"'`]*)?)["'`]/gi,
    /\bimport\s*["'`]([^"'`\\]+\.js(?:\?[^"'`]*)?)["'`]/gi,
    /\bfrom\s*["'`]([^"'`\\]+\.js(?:\?[^"'`]*)?)["'`]/gi,
  ];
  for (const expression of expressions) {
    for (const match of source.matchAll(expression)) {
      if (match[1]) paths.add(match[1]);
    }
  }
  return [...paths];
}

test("deployed Pages origin serves the project-path static contract", async ({ page }) => {
  const rootLeaks: string[] = [];
  const forbiddenRuntimeRequests: string[] = [];
  const pageUrl = new URL(hostedPagesUrl);
  const projectPath = pageUrl.pathname.endsWith("/") ? pageUrl.pathname : `${pageUrl.pathname}/`;

  page.on("request", (request) => {
    const requestUrl = new URL(request.url());
    if (requestUrl.origin === pageUrl.origin && !requestUrl.pathname.startsWith(projectPath)) {
      rootLeaks.push(requestUrl.pathname);
    }
    if (forbiddenRuntimeRequest.test(requestUrl.toString())) {
      forbiddenRuntimeRequests.push(requestUrl.toString());
    }
  });

  const htmlResponse = await page.request.get(hostedPagesUrl);
  expect(htmlResponse.ok()).toBe(true);
  expect(contentType(htmlResponse)).toMatch(/text\/html/i);
  const html = await htmlResponse.text();
  const scriptPaths = assetPathsFromHtml(html, "js");
  const cssPaths = assetPathsFromHtml(html, "css");
  expect(scriptPaths.length).toBeGreaterThan(0);
  expect(cssPaths.length).toBeGreaterThan(0);

  const scriptSources: string[] = [];
  const pendingScriptUrls = scriptPaths.map((scriptPath) => assetUrl(scriptPath, hostedPagesUrl));
  const visitedScriptUrls = new Set<string>();
  while (pendingScriptUrls.length > 0) {
    const scriptUrl = pendingScriptUrls.shift()!;
    if (visitedScriptUrls.has(scriptUrl)) continue;
    visitedScriptUrls.add(scriptUrl);
    const response = await page.request.get(scriptUrl);
    expect(response.ok()).toBe(true);
    expect(contentType(response)).toMatch(/javascript/i);
    const source = await response.text();
    scriptSources.push(source);
    for (const modulePath of javascriptModulePaths(source)) {
      const moduleUrl = new URL(modulePath, scriptUrl);
      if (moduleUrl.origin === pageUrl.origin && moduleUrl.pathname.startsWith(projectPath)) {
        pendingScriptUrls.push(moduleUrl.toString());
      }
    }
  }
  for (const cssPath of cssPaths) {
    const response = await page.request.get(assetUrl(cssPath, hostedPagesUrl));
    expect(response.ok()).toBe(true);
    expect(contentType(response)).toMatch(/text\/css/i);
  }

  await page.goto(hostedPagesUrl, { waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { name: /small model turns satellite change/i })).toBeVisible();
  await expect(page.getByRole("link", { name: /Full app \(local\)/i })).toHaveCount(0);

  const packageResponse = await page.request.get(assetUrl("demo-packages/index.json", hostedPagesUrl));
  const modelResponse = await page.request.get(assetUrl("model-manifest.json", hostedPagesUrl));
  expect(packageResponse.ok()).toBe(true);
  expect(contentType(packageResponse)).toMatch(/application\/json/i);
  expect(contentType(modelResponse)).not.toMatch(/application\/json/i);
  if (modelResponse.ok()) {
    expect(await modelResponse.text()).not.toMatch(/"schemaVersion"\s*:\s*1/);
  }

  const packagePayload = await packageResponse.json();
  expect(packagePayload.packages).toHaveLength(3);
  for (const item of packagePayload.packages) {
    expect(item.imageSrc).toMatch(/^demo-assets\//);
    const response = await page.request.get(assetUrl(item.imageSrc, hostedPagesUrl));
    expect(response.ok()).toBe(true);
    expect(contentType(response)).toMatch(/^image\//i);
  }

  expect(scriptSources.flatMap(wasmPathsFromJavaScript)).toEqual([]);
  expect(scriptSources.some((source) => /huggingface\.co|model-manifest\.json|wllama/i.test(source))).toBe(false);

  const faviconResponse = await page.request.get(assetUrl("orbit-mark.svg", hostedPagesUrl));
  expect(faviconResponse.ok()).toBe(true);
  expect(contentType(faviconResponse)).toMatch(/image\/svg/i);

  expect(rootLeaks).toEqual([]);
  expect(forbiddenRuntimeRequests).toEqual([]);
});
