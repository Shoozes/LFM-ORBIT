import { expect, type Page } from "@playwright/test";

export async function showSubtitle(page: Page, text: string, durationMs = 3000) {
  await page.evaluate((msg) => {
    let container = document.getElementById("tutorial-subtitle-container");
    if (!container) {
      container = document.createElement("div");
      container.id = "tutorial-subtitle-container";
      container.style.position = "fixed";
      container.style.bottom = "40px";
      container.style.left = "50%";
      container.style.transform = "translateX(-50%)";
      container.style.maxWidth = "80%";
      container.style.backgroundColor = "rgba(0, 0, 0, 0.85)";
      container.style.color = "#fff";
      container.style.padding = "16px 24px";
      container.style.borderRadius = "12px";
      container.style.fontSize = "20px";
      container.style.fontWeight = "600";
      container.style.fontFamily = "system-ui, sans-serif";
      container.style.textAlign = "center";
      container.style.zIndex = "99999";
      container.style.boxShadow = "0 8px 32px rgba(0, 0, 0, 0.3)";
      container.style.backdropFilter = "blur(8px)";
      container.style.transition = "opacity 0.3s ease-in-out, transform 0.3s ease-in-out";
      container.style.border = "1px solid rgba(255, 255, 255, 0.1)";
      document.body.appendChild(container);
    }

    container.style.opacity = "0";
    container.style.transform = "translateX(-50%) translateY(10px)";
    container.textContent = msg;

    void container.offsetWidth;

    container.style.opacity = "1";
    container.style.transform = "translateX(-50%) translateY(0)";
  }, text);

  await page.waitForTimeout(durationMs);
}

export async function hideSubtitle(page: Page) {
  await page.evaluate(() => {
    const container = document.getElementById("tutorial-subtitle-container");
    if (container) {
      container.style.opacity = "0";
      container.style.transform = "translateX(-50%) translateY(10px)";
    }
  });
  await page.waitForTimeout(300);
}

export async function moveMouseToHighlight(page: Page, selector: string) {
  const el = page.locator(selector).first();
  if (!(await el.isVisible())) {
    return;
  }

  const box = await el.boundingBox();
  if (!box) {
    return;
  }

  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 20 });
  await el.evaluate((target: HTMLElement) => {
    document.getElementById("tutorial-highlight")?.remove();
    const highlight = document.createElement("div");
    highlight.id = "tutorial-highlight";
    const rect = target.getBoundingClientRect();
    highlight.style.position = "fixed";
    highlight.style.top = `${rect.top - 5}px`;
    highlight.style.left = `${rect.left - 5}px`;
    highlight.style.width = `${rect.width + 10}px`;
    highlight.style.height = `${rect.height + 10}px`;
    highlight.style.border = "3px solid #10b981";
    highlight.style.borderRadius = "8px";
    highlight.style.pointerEvents = "none";
    highlight.style.zIndex = "99998";
    highlight.style.boxShadow = "0 0 15px rgba(16, 185, 129, 0.5)";
    highlight.style.transition = "opacity 0.3s";
    document.body.appendChild(highlight);
  });
}

export async function removeHighlight(page: Page) {
  await page.evaluate(() => {
    document.getElementById("tutorial-highlight")?.remove();
  });
}

export async function getMapCanvasBox(page: Page) {
  const mapCanvas = page.locator(".maplibregl-canvas").first();
  await expect(mapCanvas).toBeVisible();
  const box = await mapCanvas.boundingBox();
  if (!box) {
    throw new Error("Map canvas did not expose a bounding box.");
  }
  return box;
}

export async function drawMapBbox(
  page: Page,
  start: { x: number; y: number },
  end: { x: number; y: number },
) {
  const box = await getMapCanvasBox(page);
  await page.mouse.move(box.x + box.width * start.x, box.y + box.height * start.y);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * end.x, box.y + box.height * end.y, { steps: 20 });
  await page.mouse.up();
}
