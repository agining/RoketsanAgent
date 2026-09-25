import { readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';
import type { AnalysisData } from '../src/types/analysis';

const analysis = JSON.parse(readFileSync(new URL('../backend/analysis.json', import.meta.url), 'utf8')) as AnalysisData;

test('refresh re-fetches the single analysis source and updates generated time', async ({ page }) => {
  await page.goto('/');
  const refreshed = { ...analysis, generated_at: '2099-01-02T03:04:05Z' };
  let fetches = 0;
  await page.route('**/analysis.json*', route => {
    if (route.request().resourceType() !== 'fetch') return route.continue();
    fetches += 1; return route.fulfill({ json: refreshed });
  });
  await page.getByRole('button', { name: 'Refresh analysis data' }).click();
  await expect(page.locator('.map-top-stat.timestamp')).toContainText('2099');
  expect(fetches).toBeGreaterThan(0);
});

test('analysis fetch error is actionable and retry recovers', async ({ page }) => {
  let fail = true;
  await page.route('**/analysis.json*', route => {
    if (route.request().resourceType() !== 'fetch') return route.continue();
    return fail ? route.fulfill({ status: 503, body: 'unavailable' }) : route.fulfill({ json: analysis });
  });
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('Analysis unavailable');
  fail = false; await page.getByRole('button', { name: 'Retry Analysis' }).click();
  await expect(page.locator('.map-canvas')).toBeVisible();
});

test('right detail drawer opens from a track and escape clears selection', async ({ page }) => {
  await page.goto('/');
  const entity = analysis.entities[0];
  await page.getByRole('button', { name: new RegExp(`Open track ${entity.track_id}`) }).first().click();
  await expect(page.getByRole('complementary', { name: `Track ${entity.track_id} detail drawer` })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('complementary', { name: `Track ${entity.track_id} detail drawer` })).toHaveCount(0);
});
