import { expect, test } from '@playwright/test';

test('reports, evidence drawer and map locations follow playback and filters', async ({ page }) => {
  const errors: string[] = []; page.on('pageerror', error => errors.push(error.message));
  await page.goto('/'); await expect(page.locator('.vehicle-marker')).toHaveCount(16);
  const slider = page.getByRole('slider', { name: 'Simulated time', exact: true });
  await slider.fill(String(12 * 3600 + 25 * 60));
  await page.getByRole('tab', { name: 'Reports', exact: true }).click();
  await expect(page.locator('.report-row', { hasText: 'R001' })).toBeVisible();
  await expect(page.locator('.report-row', { hasText: 'R019' })).toHaveCount(0);
  await page.getByRole('button', { name: 'Conflicts', exact: true }).click();
  const report = page.locator('.report-row', { hasText: 'R001' }); await report.click();
  const drawer = page.getByRole('complementary', { name: 'Report investigation' });
  await expect(drawer).toContainText('Evidence contradiction'); await expect(drawer).toContainText('Original report'); await expect(drawer).toContainText('Evidence match');
  await expect(page.getByRole('button', { name: 'Select report R001' })).toHaveClass(/selected/);
  await page.getByRole('button', { name: 'Close report details' }).click();
  await page.getByRole('tab', { name: 'Layers', exact: true }).click();
  await page.getByRole('checkbox', { name: 'Report locations' }).uncheck();
  await expect(page.locator('.report-map-marker:visible')).toHaveCount(0);
  expect(errors).toEqual([]);
});
