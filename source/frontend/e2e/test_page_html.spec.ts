import { test } from '@playwright/test';
import { mkdir, writeFile } from 'fs/promises';
import { dirname } from 'path';
import { gotoApp } from './runtime';

test.skip(process.env.PLAYWRIGHT_DUMP_HTML !== "1", "Set PLAYWRIGHT_DUMP_HTML=1 to write a page HTML dump.");

test('dump html to file', async ({ page }, testInfo) => {
  if (process.env.PLAYWRIGHT_DUMP_HTML_LOGS === "1") {
    page.on('console', msg => console.log('PAGE LOG:', msg.text()));
    page.on('pageerror', exception => console.log('PAGE ERROR:', exception));
  }

  await gotoApp(page);
  await page.waitForTimeout(5000);
  const html = await page.content();
  const outPath = testInfo.outputPath('page_dump.html');
  await mkdir(dirname(outPath), { recursive: true });
  await writeFile(outPath, html, 'utf-8');
});
