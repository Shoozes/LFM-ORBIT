import { test } from '@playwright/test';
import * as fs from 'fs';

test('dump html to file', async ({ page }) => {
  page.on('console', msg => console.log('PAGE LOG:', msg.text()));
  page.on('pageerror', exception => console.log('PAGE ERROR:', exception));

  await page.goto('/');
  await page.waitForTimeout(5000);
  const html = await page.content();
  fs.writeFileSync('page_dump.html', html);
});
