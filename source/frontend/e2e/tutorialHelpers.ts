import { expect, type Locator, type Page } from "@playwright/test";

type TutorialTarget = Locator | string;

function targetLocator(page: Page, target: TutorialTarget): Locator {
  return typeof target === "string" ? page.locator(target).first() : target.first();
}

export async function showSubtitle(page: Page, text: string, durationMs = 3000) {
  await page.evaluate((msg) => {
    const highlightTerms: Record<string, string> = {
      "GROUND AGENT": "#34d399",
      "SATELLITE AGENT": "#60a5fa",
      "SPACE AGENT": "#60a5fa",
      "AI": "#f0abfc",
      "ANOMALY": "#facc15",
      "FOUND": "#facc15",
      "GRID": "#facc15",
      "FRAMES": "#c084fc",
      "ACQUISITION": "#c084fc",
      "SELECT TOOL": "#facc15",
      "TIMELAPSE": "#c084fc",
      "STATIC FRAME": "#f97316",
      "CV BOXES": "#22d3ee",
      "COMPACT PROOF JSON": "#67e8f9",
      "PROOF JSON": "#67e8f9",
      "PROOF": "#67e8f9",
      "RESULT": "#67e8f9",
      "SEMANTIC DATA": "#86efac",
      "TAGGED TRAINING DATA": "#86efac",
      "TRAINING DATA": "#86efac",
      "HIGH-STAKES": "#fb7185",
      "CLICK": "#fde047",
      "TYPE": "#fde047",
    };
    const escapeHtml = (value: string) => value
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
    const escapeRegex = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const highlighted = Object.entries(highlightTerms)
      .sort((left, right) => right[0].length - left[0].length)
      .reduce((html, [term, color]) => (
        html.replace(
          new RegExp(escapeRegex(term), "g"),
          `<span style="color:${color};font-weight:900">${term}</span>`,
        )
      ), escapeHtml(msg));

    let container = document.getElementById("tutorial-subtitle-container");
    if (!container) {
      container = document.createElement("div");
      container.id = "tutorial-subtitle-container";
      container.style.position = "fixed";
      container.style.bottom = "28px";
      container.style.left = "50%";
      container.style.transform = "translateX(-50%)";
      container.style.maxWidth = "80%";
      container.style.backgroundColor = "rgba(2, 6, 23, 0.88)";
      container.style.color = "#fff";
      container.style.padding = "14px 22px";
      container.style.borderRadius = "10px";
      container.style.fontSize = "19px";
      container.style.fontWeight = "600";
      container.style.fontFamily = "system-ui, sans-serif";
      container.style.textAlign = "center";
      container.style.zIndex = "99999";
      container.style.boxShadow = "0 8px 32px rgba(0, 0, 0, 0.3)";
      container.style.backdropFilter = "blur(8px)";
      container.style.transition = "opacity 0.3s ease-in-out, transform 0.3s ease-in-out";
      container.style.border = "1px solid rgba(255, 255, 255, 0.1)";
      container.style.lineHeight = "1.35";
      container.style.whiteSpace = "pre-line";
      container.style.pointerEvents = "none";
      document.body.appendChild(container);
    }

    container.style.opacity = "0";
    container.style.transform = "translateX(-50%) translateY(10px)";
    container.innerHTML = highlighted;

    void container.offsetWidth;

    container.style.opacity = "1";
    container.style.transform = "translateX(-50%) translateY(0)";
  }, text);

  await page.waitForTimeout(durationMs);
}

export async function showTutorialCard(
  page: Page,
  options: { title: string; body: string; tags: string[] },
  durationMs = 5000,
) {
  await page.evaluate(({ title, body, tags }) => {
    const escapeHtml = (value: string) => value
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
    document.getElementById("tutorial-final-card")?.remove();
    const card = document.createElement("div");
    card.id = "tutorial-final-card";
    card.setAttribute("data-testid", "tutorial-final-card");
    card.style.position = "fixed";
    card.style.inset = "0";
    card.style.zIndex = "100000";
    card.style.display = "flex";
    card.style.alignItems = "center";
    card.style.justifyContent = "center";
    card.style.background = "rgba(2, 6, 23, 0.58)";
    card.style.backdropFilter = "blur(4px)";
    card.innerHTML = `
      <section style="width:min(840px,78vw);border:1px solid rgba(103,232,249,0.35);background:rgba(15,23,42,0.96);box-shadow:0 24px 80px rgba(0,0,0,0.42);border-radius:12px;padding:28px 32px;color:white;font-family:system-ui,sans-serif">
        <p style="margin:0 0 10px;color:#67e8f9;font-size:12px;font-weight:800;letter-spacing:0.22em;text-transform:uppercase">Mission Result</p>
        <h2 style="margin:0;font-size:30px;line-height:1.12;font-weight:800">${escapeHtml(title)}</h2>
        <p style="margin:16px 0 0;color:#d4d4d8;font-size:16px;line-height:1.5;font-weight:600">${escapeHtml(body)}</p>
        <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:20px">
          ${tags.map((tag) => `<span style="border:1px solid rgba(134,239,172,0.36);background:rgba(22,101,52,0.28);color:#bbf7d0;border-radius:999px;padding:7px 10px;font-size:11px;font-weight:800;letter-spacing:0.12em;text-transform:uppercase">${escapeHtml(tag)}</span>`).join("")}
        </div>
      </section>
    `;
    document.body.appendChild(card);
  }, options);
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

export async function showClickPulse(
  page: Page,
  target: TutorialTarget,
  label = "CLICK",
) {
  const el = targetLocator(page, target);
  await expect(el).toBeVisible();
  const box = await el.boundingBox();
  if (!box) {
    return;
  }

  const x = box.x + box.width / 2;
  const y = box.y + box.height / 2;
  await page.mouse.move(x, y, { steps: 12 });
  await page.evaluate(({ xPos, yPos, text }) => {
    const styleId = "tutorial-click-pulse-style";
    if (!document.getElementById(styleId)) {
      const style = document.createElement("style");
      style.id = styleId;
      style.textContent = `
        @keyframes tutorial-click-ring {
          0% { opacity: 0; transform: translate(-50%, -50%) scale(0.42); }
          18% { opacity: 1; transform: translate(-50%, -50%) scale(0.7); }
          100% { opacity: 0; transform: translate(-50%, -50%) scale(1.55); }
        }
        @keyframes tutorial-click-dot {
          0%, 100% { transform: translate(-50%, -50%) scale(1); }
          50% { transform: translate(-50%, -50%) scale(1.18); }
        }
      `;
      document.head.appendChild(style);
    }

    const pulse = document.createElement("div");
    pulse.className = "tutorial-click-pulse";
    pulse.style.position = "fixed";
    pulse.style.left = `${xPos}px`;
    pulse.style.top = `${yPos}px`;
    pulse.style.zIndex = "100001";
    pulse.style.pointerEvents = "none";
    pulse.innerHTML = `
      <div style="position:absolute;left:0;top:0;width:78px;height:78px;border:4px solid #fde047;border-radius:999px;box-shadow:0 0 36px rgba(253,224,71,0.72);animation:tutorial-click-ring 1320ms ease-out both"></div>
      <div style="position:absolute;left:0;top:0;width:18px;height:18px;background:#fde047;border:2px solid #111827;border-radius:999px;box-shadow:0 0 24px rgba(253,224,71,0.95);animation:tutorial-click-dot 520ms ease-out both"></div>
      <div style="position:absolute;left:34px;top:28px;background:rgba(17,24,39,0.94);color:#fde047;border:1px solid rgba(253,224,71,0.65);border-radius:999px;padding:6px 9px;font-family:system-ui,sans-serif;font-size:11px;font-weight:900;letter-spacing:0.17em;text-transform:uppercase;white-space:nowrap">${text}</div>
    `;
    document.body.appendChild(pulse);
    window.setTimeout(() => pulse.remove(), 1_560);
  }, { xPos: x, yPos: y, text: label });
  await page.waitForTimeout(640);
}

export async function clickWithPulse(
  page: Page,
  target: TutorialTarget,
  label = "CLICK",
  pauseAfterMs = 520,
) {
  const el = targetLocator(page, target);
  await showClickPulse(page, el, label);
  await el.click();
  await page.waitForTimeout(pauseAfterMs);
}

export async function typeLikeOperator(
  page: Page,
  target: TutorialTarget,
  text: string,
  options: { label?: string; delayMs?: number; pauseAfterMs?: number } = {},
) {
  const el = targetLocator(page, target);
  await expect(el).toBeVisible();
  await showClickPulse(page, el, options.label ?? "TYPE");
  await el.click();
  await el.fill("");
  await el.pressSequentially(text, { delay: options.delayMs ?? 38 });
  await page.waitForTimeout(options.pauseAfterMs ?? 850);
}

export async function removeHighlight(page: Page) {
  await page.evaluate(() => {
    document.getElementById("tutorial-highlight")?.remove();
    document.querySelectorAll(".tutorial-click-pulse").forEach((node) => node.remove());
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
