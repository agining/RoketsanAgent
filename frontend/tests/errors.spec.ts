import { expect, test } from '@playwright/test';
import { mockApi } from './support/mock-api';

test('API down shows a clear error and retry recovers', async ({ page }) => {
  let down = true;
  await mockApi(page);
  await page.route('**/api/**', route => down ? route.fulfill({ status: 500, contentType: 'text/plain', body: '' }) : route.fallback());
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('Analiz verisi alınamadı');
  await expect(page.getByRole('alert')).toContainText('8000 portundaki servisin çalıştığını kontrol edin');
  down = false;
  await page.getByRole('button', { name: 'Tekrar Dene' }).click();
  await expect(page.locator('.analysis-track-marker').first()).toBeAttached();
});

test('an API contract change is reported with the endpoint name', async ({ page }) => {
  await mockApi(page, state => { (state.trackingData as { zones: unknown }).zones = [{ name: 'bozuk' }]; });
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('/api/tracking-data');
});
