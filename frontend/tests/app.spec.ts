import { expect, test } from '@playwright/test';
import { mockApi } from './support/mock-api';

test('loads everything from the API and renders tracks, detections and summary', async ({ page }) => {
  const errors: string[] = []; page.on('pageerror', error => errors.push(error.message));
  const localData: string[] = []; page.on('request', request => { if (/mock_data|backend\/|analysis\.json|tracks\.csv/.test(request.url())) localData.push(request.url()); });
  const { state, calls } = await mockApi(page);
  await page.goto('/');
  await expect(page.locator('.analysis-track-marker')).toHaveCount(state.trackingData.tracks.length);
  const untracked = state.frames.flatMap(frame => frame.vehicles).filter(vehicle => vehicle.track_id === null);
  await expect(page.locator('.untracked-map-marker')).toHaveCount(untracked.length);
  await expect(page.locator('.zone-marker')).toHaveCount(state.trackingData.zones.length);
  await expect(page.locator('.map-top-stat').nth(1)).toContainText(String(state.trackingData.tracks.length));
  const highCritical = state.alerts.filter(alert => alert.risk_level === 'YUKSEK' || alert.risk_level === 'KRITIK').length;
  await expect(page.locator('.risk-total')).toContainText(String(highCritical));
  await expect(page.locator('.pending-total')).toContainText('1');
  for (const path of ['/api/summary', '/api/tracking-data', '/api/frames', '/api/reports', '/api/alerts', '/api/assessments', '/api/reviews'])
    expect(calls.some(call => call.path === path)).toBe(true);
  expect(calls.filter(call => call.path.startsWith('/api/frames/'))).toHaveLength(state.frames.length);
  expect(localData).toEqual([]);

  await page.getByRole('button', { name: 'Operasyon Özeti' }).click();
  const summary = page.getByRole('region', { name: 'Operasyon özeti' });
  await expect(summary).toContainText(`Kritik${state.summary.frame_risk_counts.KRITIK}`);
  await expect(summary).toContainText('Saha raporu hükümleri');
  await page.getByRole('button', { name: /Öncelikli Araçlar/ }).click();
  await expect(page.getByRole('region', { name: 'Öncelikli araç kayıtları' }).locator(':scope > div > button')).toHaveCount(state.alerts.length);
  expect(errors).toEqual([]);
});

test('track marker opens the API detail with decision, features and reports', async ({ page }) => {
  await mockApi(page);
  await page.goto('/');
  await page.getByRole('button', { name: /Tüm İz Kayıtları/ }).click();
  const explorer = page.getByRole('article', { name: 'Tüm iz kayıtları listesi' });
  await explorer.getByRole('combobox', { name: 'Risk filtresi' }).selectOption('CRITICAL');
  await expect(explorer.locator('tbody tr')).toHaveCount(2);
  await explorer.getByRole('button', { name: 'T0106 iz detayını aç' }).click();
  const detail = page.getByRole('complementary', { name: 'Araç detayları' });
  await expect(detail.locator('.entity-detail-title')).toContainText('T0106');
  await expect(detail.locator('.entity-detail-title')).toContainText('Kritik');
  for (const heading of ['Risk Kararı', 'Senaryo ve Gerekçeler', 'Gözlem', 'Hareket Öznitelikleri', 'Ajan Değerlendirmesi', 'Anlık Konum', 'Saha Raporları', 'Mesafe Geçmişi'])
    await expect(detail.getByRole('heading', { name: heading })).toBeVisible();
  await expect(detail).toContainText('Doğrudan hızlı yaklaşma');
  await expect(detail.locator('.entity-history-table').last()).toContainText('m');
  await expect(page.locator('.analysis-track-marker[data-track-id="T0106"]')).toHaveAttribute('aria-pressed', 'true');
});

test('map filters and layers work on API data; mobile layout stays usable', async ({ page }) => {
  const { state } = await mockApi(page);
  await page.goto('/');
  await page.getByRole('combobox', { name: 'Harita risk filtresi' }).selectOption('CRITICAL');
  await expect(page.locator('.map-filter-result')).toContainText(`2 / ${state.trackingData.tracks.length} iz görünür`);
  await page.getByRole('combobox', { name: 'Harita risk filtresi' }).selectOption('ALL');
  await page.getByRole('checkbox', { name: 'Bölgeler', exact: true }).first().uncheck();
  await expect(page.locator('.zone-marker').first()).toBeHidden();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator('.map-canvas')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
