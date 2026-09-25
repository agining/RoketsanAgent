import { readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';
import type { AnalysisData } from '../src/types/analysis';

const analysis = JSON.parse(readFileSync(new URL('../backend/analysis.json', import.meta.url), 'utf8')) as AnalysisData;

test('all tracks uses dynamic entities and opens complete backend detail', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: /All Tracks/ }).click();
  const explorer = page.getByRole('article', { name: 'All tracks' });
  await expect(explorer.locator('tbody tr')).toHaveCount(analysis.entities.length);
  const highCount = analysis.entities.filter(entity => entity.risk.assessment?.risk_level === 'HIGH').length;
  await explorer.getByRole('combobox', { name: 'Risk filter' }).selectOption('HIGH');
  await expect(explorer.locator('tbody tr')).toHaveCount(highCount);
  await explorer.getByRole('button', { name: 'Clear', exact: true }).click();
  const entity = analysis.entities.find(item => !item.vehicle_class.consistent) ?? analysis.entities[0];
  await explorer.getByRole('textbox', { name: 'Search analyzed tracks' }).fill(entity.track_id);
  await explorer.getByRole('button', { name: `Open track ${entity.track_id}` }).click();
  await expect(page.locator(`.analysis-track-marker[data-track-id="${entity.track_id}"]`)).toHaveAttribute('aria-pressed', 'true');
  const detail = page.getByRole('complementary', { name: 'Vehicle details' });
  if (!entity.vehicle_class.consistent) await expect(detail).toContainText('Vehicle Classification Uncertain');
  for (const heading of ['Identity', 'Current Position', 'Current Movement', 'Behavior', 'Risk Assessment', 'Current Evidence', 'Historical Evidence', 'Movement History', 'Behavior History']) await expect(detail.getByText(heading, { exact: true }).first()).toBeVisible();
  await expect(detail).toContainText('Field reports are corroborating evidence and are not treated as authoritative truth.');
});

test('null risk, null ETA and empty reports remain safe', async ({ page }) => {
  const target = analysis.entities.find(entity => entity.latest_movement.eta_min === null && entity.reports.length === 0) ?? analysis.entities[0];
  const modified: AnalysisData = { ...analysis, entities: analysis.entities.map(entity => entity.track_id === target.track_id ? { ...entity, risk: { ...entity.risk, assessment: null, error: 'Assessment unavailable for this run.' }, latest_behavior: null, latest_movement: { ...entity.latest_movement, eta_min: null }, reports: [] } : entity) };
  await page.route('**/analysis.json*', route => route.request().resourceType() === 'fetch' ? route.fulfill({ json: modified }) : route.continue());
  await page.goto('/');
  await page.getByRole('button', { name: /All Tracks/ }).click();
  const explorer = page.getByRole('article', { name: 'All tracks' });
  await explorer.getByRole('textbox', { name: 'Search analyzed tracks' }).fill(target.track_id);
  await explorer.getByRole('button', { name: `Open track ${target.track_id}` }).click();
  const detail = page.getByRole('complementary', { name: 'Vehicle details' });
  await expect(detail).toContainText('UNKNOWN');
  await expect(detail).toContainText('Risk analysis error');
  await expect(detail.locator('.entity-detail-section', { hasText: 'Current Movement' })).toContainText('N/A');
  await expect(detail).toContainText('No field reports');
});
