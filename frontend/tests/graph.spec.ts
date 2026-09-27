import { expect, test } from '@playwright/test';
import { mockApi } from './support/mock-api';
import { graphSnapshot } from './fixtures/graph-snapshot';

test('game graph analysis is opt-in, selectable and uses the requested window', async ({ page }, testInfo) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await mockApi(page);
  await page.route(/^https:\/\/tiles\.openfreemap\.org\//, route => route.abort());
  const calls: string[] = [];
  await page.route('**/api/graph-analysis*', route => {
    calls.push(route.request().url());
    const url = new URL(route.request().url());
    return route.fulfill({ json: { ...graphSnapshot,
      analysis_start: url.searchParams.get('start_time') ?? graphSnapshot.analysis_start,
      analysis_end: url.searchParams.get('end_time') ?? graphSnapshot.analysis_end,
    } });
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Harita panelini aç', exact: true }).click();
  const panel = page.getByRole('region', { name: 'Bölgesel Anomali Analizini Başlat' });
  await expect(panel.getByRole('button', { name: 'Bölgesel Anomali Analizini Başlat' })).toBeVisible();
  expect(calls).toHaveLength(0);
  await panel.getByRole('button', { name: 'Bölgesel Anomali Analizini Başlat' }).click();
  await panel.locator('.graph-region-row').click();
  await expect(panel.getByRole('article', { name: 'Seçili anomali bölgesi' })).toContainText('Bölge 1');
  await panel.getByText('Teknik ayrıntılar', { exact: true }).click();
  await expect(panel.getByRole('table', { name: 'Anomali skor bileşenleri' })).toContainText('Düzeltilmiş lift');
  await page.screenshot({ path: testInfo.outputPath('game-graph-panel.png'), fullPage: true });
  await panel.getByLabel('Analiz başlangıç zamanı').fill('10:30');
  await panel.getByLabel('Analiz bitiş zamanı').fill('11:30');
  await panel.getByRole('button', { name: 'Aralığı analiz et' }).click();
  await expect.poll(() => calls.some(url => url.includes('start_time=10%3A30') && url.includes('end_time=11%3A30'))).toBe(true);
  await expect(panel.locator('.graph-summary')).toContainText('10:30 – 11:30');
  await expect(panel.getByRole('table')).toHaveCount(0);
  const canvas = page.getByLabel('Zaman çizelgesi oynatmalı analiz haritası');
  const bounds = await canvas.boundingBox();
  await page.screenshot({ path: testInfo.outputPath('game-graph-before-map-click.png'), fullPage: true });
  await expect(async () => {
    // Select the visible region rim; the existing base DOM marker overlaps its centre.
    await canvas.click({ position: { x: bounds!.width / 2 - 12, y: bounds!.height / 2 - 8 } });
    await expect(panel.getByRole('article', { name: 'Seçili anomali bölgesi' })).toBeVisible({ timeout: 1000 });
  }).toPass({ timeout: 10000 });
  await panel.getByRole('button', { name: 'Anomali tespitini kapat' }).click();
  await expect(panel.getByRole('table')).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('graph request failure leaves existing tracks usable', async ({ page }) => {
  await mockApi(page);
  await page.route(/^https:\/\/tiles\.openfreemap\.org\//, route => route.abort());
  await page.route('**/api/graph-analysis*', route => route.fulfill({ status: 503, json: { detail: 'Graph unavailable' } }));
  await page.goto('/');
  await page.getByRole('button', { name: 'Harita panelini aç', exact: true }).click();
  await page.getByRole('button', { name: 'Bölgesel Anomali Analizini Başlat' }).click();
  await expect(page.getByRole('alert').filter({ hasText: 'Graph unavailable' })).toBeVisible();
  await expect(page.locator('.analysis-track-marker').first()).toBeAttached();
});
