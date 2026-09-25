import { readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';
import type { AnalysisData } from '../src/types/analysis';

const analysis = JSON.parse(readFileSync(new URL('../backend/analysis.json', import.meta.url), 'utf8')) as AnalysisData;

test('map-first toolbar and floating summary render backend values', async ({ page }) => {
  await page.goto('/');
  const summary = analysis.operation_summary;
  await expect(page.locator('.map-top-stat.timestamp')).toBeVisible();
  await expect(page.locator('.map-top-stat', { hasText: 'TRACKED' })).toContainText(String(summary.tracked_entity_count));
  await expect(page.locator('.risk-total')).toContainText(String(summary.risk_counts.HIGH + summary.risk_counts.CRITICAL));
  await page.getByRole('button', { name: 'Operational Summary' }).click();
  const panel = page.getByRole('region', { name: 'Operational summary' });
  await expect(panel).toContainText(`Approaching${summary.current_state_counts.approaching_base}`);
  await expect(panel).toContainText(`Loitering${summary.current_state_counts.loitering}`);
  await expect(panel).toContainText('Intelligence inconsistencies');
  await page.getByRole('button', { name: 'Priority Tracks', exact: false }).click();
  await expect(page.getByRole('region', { name: 'Priority tracks' }).locator(':scope > div > button')).toHaveCount(summary.priority_entities.length);
});

test('zero critical and empty priority states render without fabricated data', async ({ page }) => {
  const emptyPriority: AnalysisData = { ...analysis, operation_summary: { ...analysis.operation_summary, risk_counts: { ...analysis.operation_summary.risk_counts, HIGH: 0, CRITICAL: 0 }, priority_entities: [] } };
  await page.route('**/analysis.json*', route => route.request().resourceType() === 'fetch' ? route.fulfill({ json: emptyPriority }) : route.continue());
  await page.goto('/');
  await expect(page.locator('.risk-total')).toContainText('0');
  await page.getByRole('button', { name: 'Priority Tracks', exact: false }).click();
  await expect(page.getByText('No HIGH or CRITICAL priority entities in this analysis.', { exact: true })).toBeVisible();
});
