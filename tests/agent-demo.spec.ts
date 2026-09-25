import { expect, test } from '@playwright/test';

test('demo mode, alert center, reasoning trace and local SITREP work together', async ({ page }) => {
  const errors: string[] = []; page.on('pageerror', error => errors.push(error.message));
  await page.goto('/'); await expect(page.locator('.vehicle-marker')).toHaveCount(16);
  await page.getByRole('slider', { name: 'Simulated time', exact: true }).fill(String(12 * 3600 + 30 * 60));
  await page.getByRole('button', { name: 'Demo', exact: true }).click();
  await expect(page.locator('.app-shell')).toHaveClass(/demo-mode/);
  await expect(page.getByRole('region', { name: 'alerts panel' })).toBeVisible();
  await expect(page.locator('.agent-alert.alert-untracked').first()).toBeVisible();
  await expect(page.getByText('Reasoning trace', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'SITREP', exact: true }).click();
  await page.getByRole('button', { name: 'Generate current SITREP' }).click();
  await expect(page.locator('.sitrep-output')).toContainText('SITREP 12:30');
  await page.getByRole('button', { name: 'Agent', exact: true }).click();
  await expect(page.getByRole('button', { name: 'En kritik araç hangisi?' })).toBeVisible();
  await expect(page.getByRole('textbox', { name: 'Agent message', exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});
