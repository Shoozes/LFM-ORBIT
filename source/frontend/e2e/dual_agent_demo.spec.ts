import { test, expect, Page } from "@playwright/test";

// Helper to inject beautiful subtitles at the bottom of the screen
async function showSubtitle(page: Page, text: string, durationMs: number = 3000) {
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
    
    // Animate in
    container.style.opacity = "0";
    container.style.transform = "translateX(-50%) translateY(10px)";
    container.innerHTML = msg;
    
    // Force reflow
    void container.offsetWidth;
    
    container.style.opacity = "1";
    container.style.transform = "translateX(-50%) translateY(0)";
  }, text);

  await page.waitForTimeout(durationMs);
}

async function hideSubtitle(page: Page) {
  await page.evaluate(() => {
    const container = document.getElementById("tutorial-subtitle-container");
    if (container) {
      container.style.opacity = "0";
      container.style.transform = "translateX(-50%) translateY(10px)";
    }
  });
  await page.waitForTimeout(300);
}

async function moveMouseToHighlight(page: Page, selector: string) {
  const el = page.locator(selector).first();
  if (await el.isVisible()) {
    const box = await el.boundingBox();
    if (box) {
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 20 });
      await el.evaluate((target: HTMLElement) => {
        const highlight = document.createElement("div");
        highlight.id = "tutorial-highlight";
        const rect = target.getBoundingClientRect();
        highlight.style.position = "fixed";
        highlight.style.top = `${rect.top - 5}px`;
        highlight.style.left = `${rect.left - 5}px`;
        highlight.style.width = `${rect.width + 10}px`;
        highlight.style.height = `${rect.height + 10}px`;
        highlight.style.border = "3px solid #10b981"; // Emerald
        highlight.style.borderRadius = "8px";
        highlight.style.pointerEvents = "none";
        highlight.style.zIndex = "99998";
        highlight.style.boxShadow = "0 0 15px rgba(16, 185, 129, 0.5)";
        highlight.style.transition = "opacity 0.3s";
        document.body.appendChild(highlight);
      });
    }
  }
}

async function removeHighlight(page: Page) {
    await page.evaluate(() => {
        const h = document.getElementById("tutorial-highlight");
        if (h) h.remove();
    });
}

test.use({ 
  video: "on", 
  viewport: { width: 1440, height: 900 }
});

test("Tutorial: Dual-Agent Architecture Demo", async ({ page }) => {
  // Increase test timeout
  test.setTimeout(120_000);

  // 1. App initialization
  await page.goto("/");
  await showSubtitle(page, "LFM Orbit utilizes a powerful Dual-Agent AI architecture.", 4000);
  await page.waitForTimeout(3000);
  
  await showSubtitle(page, "To save bandwidth, a Satellite Agent resides on the satellite computing edge.", 4000);

  // 2. Mission Setup
  await page.locator("[data-testid='tab-mission']").click();
  await page.waitForTimeout(1000);
  
  // Drawing area
  await page.getByText("Draw Area on Map").click();
  
  await showSubtitle(page, "We dispatch a mission specifying coordinates and objectives...", 3000);
  const viewportSize = page.viewportSize() || { width: 1440, height: 900 };
  await page.mouse.move(viewportSize.width / 2 - 100, viewportSize.height / 2 - 100);
  await page.mouse.down();
  await page.mouse.move(viewportSize.width / 2 + 100, viewportSize.height / 2 + 100, { steps: 20 });
  await page.mouse.up();
  await page.waitForTimeout(1000);

  await page.fill('textarea', "Scan this region for recent clear-cut deforestation.");
  await page.waitForTimeout(1000);
  
  await moveMouseToHighlight(page, "button:has-text('Launch Mission')");
  await page.getByText("Launch Mission").click();
  await removeHighlight(page);
  
  await showSubtitle(page, "The parameters beam up to the Satellite Agent instantly.", 3000);

  // 3. Switch to Agent UI
  await page.locator("[data-testid='tab-agents']").click();
  await page.waitForTimeout(1000);

  await showSubtitle(page, "The Ground Agent confirms the payload transmission.", 4000);
  await page.waitForTimeout(4000);

  await showSubtitle(page, "The Satellite Agent begins dropping 99.9% of normal uninteresting telemetry.", 4000);
  await page.waitForTimeout(7000);

  await showSubtitle(page, "When the Satellite Agent detects a true structural anomaly, it opens a secure dialogue.", 5000);
  await page.waitForTimeout(7000);

  await showSubtitle(page, "Only extremely lightweight JSON byte-strings are transmitted back to Earth.", 5000);
  await page.waitForTimeout(7000);

  await showSubtitle(page, "The Ground Validator Agent processes these flags natively using Vision Language Models.", 5000);
  await page.waitForTimeout(7000);

  await showSubtitle(page, "This architecture brings near-zero latency, robust intelligence, and staggering operational savings.", 5000);
  await page.waitForTimeout(5000);
  
  // Highlight SAT agent message response
  await showSubtitle(page, "Workflow Complete: Satellite Agent confirmed anomalies and successfully alerted Ground Control.", 5000);
  await moveMouseToHighlight(page, "div.rounded.border:has(span:text-is('SAT'))");
  
  // Wait to allow viewer to observe the highlighted chat
  await page.waitForTimeout(5000);
  
  await removeHighlight(page);
  await hideSubtitle(page);
  
  // Let the chat finish scrolling for aesthetic purposes
  await page.waitForTimeout(2000);
});
