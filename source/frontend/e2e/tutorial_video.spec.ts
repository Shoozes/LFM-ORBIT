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

  // Wait so viewer can read it
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

// Emulate realistic mouse cursor movements securely
async function moveMouseToHighlight(page: Page, selector: string) {
  const el = page.locator(selector).first();
  if (await el.isVisible()) {
    const box = await el.boundingBox();
    if (box) {
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 20 });
      // Add a subtle glowing ring around highlighted element
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

test("Tutorial: How LFM Orbit AI Detects Deforestation", async ({ page }) => {
  // Increase test timeout since this is a slow, scripted tutorial video
  test.setTimeout(90_000);

  // 1. App initialization
  await page.goto("/");
  await showSubtitle(page, "Welcome to LFM Orbit. Let's see how our autonomous AI agents detect deforestation.", 4000);
  // Wait for initialization
  await page.waitForTimeout(6000);
  await showSubtitle(page, "The app connects to multi-modality Vision Language Models and live Sentinel-2 streams.", 4000);

  // 2. Mission Setup
  await showSubtitle(page, "First, we establish a target region and dispatch a natural language mission.", 3000);
  
  // Highlighting Mission Tab
  await moveMouseToHighlight(page, "[data-testid='tab-mission']");
  await page.waitForTimeout(1000);
  await page.locator("[data-testid='tab-mission']").click();
  await removeHighlight(page);
  
  // Drawing area
  await page.waitForTimeout(1000);
  await moveMouseToHighlight(page, "button:has-text('Draw Area on Map')");
  await page.waitForTimeout(1000);
  await page.getByText("Draw Area on Map").click();
  await removeHighlight(page);
  
  await showSubtitle(page, "We drag a bounding box directly on the map to define our area of interest...", 2000);
  const viewportSize = page.viewportSize() || { width: 1440, height: 900 };
  await page.mouse.move(viewportSize.width / 2 - 100, viewportSize.height / 2 - 100);
  await page.mouse.down();
  await page.mouse.move(viewportSize.width / 2 + 100, viewportSize.height / 2 + 100, { steps: 20 });
  await page.mouse.up();
  await page.waitForTimeout(1000);

  await showSubtitle(page, "Next, we instruct the AI on what to look for...", 2000);
  await page.fill('textarea', "Scan this region for recent clear-cut deforestation.");
  await page.waitForTimeout(1000);
  
  await moveMouseToHighlight(page, "button:has-text('Launch Mission')");
  await page.waitForTimeout(1000);
  await page.getByText("Launch Mission").click();
  await removeHighlight(page);
  
  await showSubtitle(page, "The Mission is now ACTIVE.", 3000);

  // 3. Agent Dialogue (The AI logic)
  await page.waitForTimeout(500);

  await showSubtitle(page, "Behind the scenes, the Ground Agent dispatches parameters to the Satellite Agent.", 4000);
  await page.locator("[data-testid='tab-agents']").click();
  await page.waitForTimeout(3000);

  // 4. Alerts and Findings
  await showSubtitle(page, "As the satellite scans Sentinel 2 bands, anomalies (like dropping NDVI/NIR) are flagged.", 4000);
  
  await page.locator("[data-testid='tab-logs']").click();
  await showSubtitle(page, "The Satellite agent compresses only the flagged cells to Ground Control, saving bandwidth.", 4000);
  
  // Wait for at least 1 alert to be populated
  await page.waitForSelector("[data-testid='alert-button']", { timeout: 25_000 });
  
  const firstAlert = page.locator("[data-testid='alert-button']").first();
  await expect(firstAlert).toBeVisible({ timeout: 5000 });
  
  await showSubtitle(page, "We can expand a flagged area to see the exact spectral band changes...", 3000);
  await firstAlert.click();

  await page.waitForTimeout(2000);
  
  await showSubtitle(page, "Here we see the temporal shifts in Near Infrared (NIR) and Red bands.", 4000);
  
  // AI verification
  await showSubtitle(page, "We can then ask an offline VLM model to verify these anomalous pixels.", 4000);
  await moveMouseToHighlight(page, "button:has-text('Analyze')");
  await page.waitForTimeout(1000);
  await page.locator("[data-testid='analyze-button']").click();
  await removeHighlight(page);
  
  await expect(page.getByText("offline_lfm_v1")).toBeVisible({ timeout: 15_000 });
  await showSubtitle(page, "The VLM confirms structural loss consistent with deforestation.", 4000);
  
  // 5. Timelapse Context Menu
  await showSubtitle(page, "Finally, we can visualize the specific area via our Orbital Timelapse feature.", 4000);
  
  const targetX = viewportSize.width / 2 + 50;
  const targetY = viewportSize.height / 2 + 50;
  await page.mouse.move(targetX, targetY);
  await page.mouse.click(targetX, targetY, { button: 'right' });
  await page.waitForTimeout(1000);
  
  await page.getByText("▷ Generate Temporal Timelapse").click();
  
  await page.waitForTimeout(2000);
  await showSubtitle(page, "The AI automatically extracts frames via FFMpeg to build a true history.", 4000);
  
  await page.waitForTimeout(3000);
  await showSubtitle(page, "And that's how LFM Orbit achieves efficient, verified earth observation.", 4000);
  await hideSubtitle(page);
  
  // Linger for a moment to close out the video cleanly
  await page.waitForTimeout(2000);
});
