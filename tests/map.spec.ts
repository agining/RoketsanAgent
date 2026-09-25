import { readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';
import type { AnalysisData } from '../src/types/analysis';

const analysis = JSON.parse(readFileSync(new URL('../backend/analysis.json', import.meta.url), 'utf8')) as AnalysisData;

test('map renders analysis coordinates and opens track detail from a semantic marker', async ({ page }) => {
  const errors: string[] = []; page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await expect(page.locator('.analysis-track-marker')).toHaveCount(analysis.entities.length);
  await expect(page.locator('.untracked-map-marker')).toHaveCount(analysis.untracked_observations.length);
  await expect(page.locator('.zone-marker')).toHaveCount(analysis.zones.length);
  await expect(page.locator('.base-marker')).toHaveCount(1);
  const entity = analysis.entities[0];
  const marker = page.locator('.analysis-track-marker', { hasText: entity.track_id });
  await marker.hover();
  const popup = page.locator('.vehicle-tooltip');
  await expect(popup).toContainText(entity.track_id);
  await expect(popup).toContainText(entity.vehicle_class.canonical.toUpperCase());
  await expect(popup).toContainText('State at 12:00');
  await expect(popup).toContainText('Overall risk');
  await marker.click();
  await expect(page.locator('.entity-detail-title')).toContainText(entity.track_id);
  await expect(marker).toHaveAttribute('aria-pressed', 'true');
  expect(errors).toEqual([]);
});

test('map layer controls and mobile layout remain usable', async ({ page }) => {
  await page.goto('/');
  const highCount = analysis.entities.filter(entity => entity.risk.assessment?.risk_level === 'HIGH').length;
  await page.getByRole('combobox', { name: 'Map risk filter' }).selectOption('HIGH');
  await expect(page.locator('.analysis-track-marker:visible')).toHaveCount(highCount);
  await page.getByRole('combobox', { name: 'Map risk filter' }).selectOption('ALL');
  await page.getByRole('checkbox', { name: 'Tracks', exact: true }).uncheck();
  await expect(page.locator('.analysis-track-marker').first()).toBeHidden();
  await page.getByRole('checkbox', { name: 'Tracks', exact: true }).check();
  await page.getByRole('checkbox', { name: 'Zones', exact: true }).uncheck();
  await expect(page.locator('.zone-marker').first()).toBeHidden();
  await page.getByRole('checkbox', { name: 'Base', exact: true }).uncheck();
  await expect(page.locator('.base-marker')).toBeHidden();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator('.map-canvas')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
