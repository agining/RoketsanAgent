import { readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';
import type { AnalysisData } from '../src/types/analysis';

const analysis = JSON.parse(readFileSync(new URL('../backend/analysis.json', import.meta.url), 'utf8')) as AnalysisData;

test('untracked observations stay separate and never receive fabricated risk', async ({ page }) => {
  await page.goto('/');
  const section = page.locator('.map-untracked-list');
  await expect(section.locator('article')).toHaveCount(analysis.untracked_observations.length);
  if (analysis.untracked_observations.length) {
    await expect(section).toContainText(analysis.untracked_observations[0].detection.class.toUpperCase());
    await expect(section.locator('.entity-risk')).toHaveCount(0);
  }
});

test('empty untracked observations show a stable empty state', async ({ page }) => {
  const empty: AnalysisData = { ...analysis, untracked_observations: [], operation_summary: { ...analysis.operation_summary, untracked_observation_count: 0 } };
  await page.route('**/analysis.json*', route => route.request().resourceType() === 'fetch' ? route.fulfill({ json: empty }) : route.continue());
  await page.goto('/');
  await expect(page.getByText('No untracked detections.', { exact: true })).toBeVisible();
  await expect(page.locator('.untracked-map-marker')).toHaveCount(0);
});
