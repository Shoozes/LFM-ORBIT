import { expect, test } from '@playwright/test';
import { mkdir, writeFile } from 'fs/promises';
import { dirname } from 'path';
import { gotoApp } from './runtime';

test.skip(process.env.PLAYWRIGHT_DUMP_HTML !== "1", "Set PLAYWRIGHT_DUMP_HTML=1 to write a page HTML dump.");

test('dump html to file', async ({ page }, testInfo) => {
  const consoleLines: string[] = [];
  if (process.env.PLAYWRIGHT_DUMP_HTML_LOGS === "1") {
    page.on('console', msg => consoleLines.push(`PAGE LOG: ${msg.text()}`));
    page.on('pageerror', exception => consoleLines.push(`PAGE ERROR: ${exception.message}`));
  }

  await gotoApp(page);
  await expect(page.getByText("Mission").first()).toBeVisible({ timeout: 10_000 });
  const html = await page.content();
  const outPath = testInfo.outputPath('page_dump.html');
  await mkdir(dirname(outPath), { recursive: true });
  await writeFile(outPath, html, 'utf-8');
  if (consoleLines.length > 0) {
    await writeFile(testInfo.outputPath('page_dump_console.log'), `${consoleLines.join('\n')}\n`, 'utf-8');
  }
});
