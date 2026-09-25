import { expect, test } from '@playwright/test';
test('keyboard navigation, panel resizing, commands and fullscreen timeline', async ({ page }, testInfo) => {
  const errors: string[] = []; page.on('pageerror', error => errors.push(error.message));
  await page.goto('/'); await expect(page.locator('.vehicle-marker')).toHaveCount(16);
  const slider = page.getByRole('slider', { name: 'Simulated time', exact: true });
  const start = Number(await slider.inputValue());
  await page.locator('.maplibregl-canvas').focus();
  await page.keyboard.press('ArrowRight'); expect(Number(await slider.inputValue())).toBe(start + 60);
  await page.keyboard.press('ArrowLeft'); expect(Number(await slider.inputValue())).toBe(start);
  await page.keyboard.press('Space'); await expect(page.getByRole('button', { name: 'Pause', exact: true })).toBeVisible();
  await page.keyboard.press('Space'); await expect(page.getByRole('button', { name: 'Play', exact: true })).toBeVisible();
  await page.keyboard.press('/'); const search = page.getByRole('textbox', { name: 'Search vehicle tracks' }); await expect(search).toBeFocused();
  await search.fill('T0002'); await page.locator('.track-row').click();
  await page.locator('.maplibregl-canvas').focus(); await page.keyboard.press('f');
  await expect(page.getByRole('button', { name: 'Follow', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await page.keyboard.press('f');
  const left = page.getByRole('separator', { name: 'Resize left panel' });
  await left.focus(); await page.keyboard.press('ArrowRight'); await expect(left).toHaveAttribute('aria-valuenow', '260');
  const right = page.getByRole('separator', { name: 'Resize right panel' });
  const bounds = (await right.boundingBox())!;
  await page.mouse.move(bounds.x + 3, bounds.y + 50); await page.mouse.down(); await page.mouse.move(bounds.x - 27, bounds.y + 50); await page.mouse.up();
  await expect(right).toHaveAttribute('aria-valuenow', '330');
  await page.getByRole('button', { name: 'Collapse inspector', exact: true }).click();
  await expect(page.getByRole('complementary', { name: 'Vehicle details' })).toHaveCount(0);
  await page.getByRole('button', { name: 'Toggle inspector', exact: true }).click();
  await expect(page.getByRole('complementary', { name: 'Vehicle details' })).toBeVisible();
  await page.keyboard.press('Control+k'); const command = page.getByRole('combobox', { name: 'Search commands' }); await expect(command).toBeFocused();
  await command.fill('T0005'); await page.keyboard.press('Enter'); await expect(page.locator('.detail-title')).toContainText('T0005');
  await page.keyboard.press('Control+k'); await command.fill('Toggle zones'); await page.keyboard.press('Enter'); await expect(page.locator('.zone-marker').first()).toBeHidden();
  await page.keyboard.press('Control+k'); await page.keyboard.press('Escape'); await expect(page.getByRole('dialog')).toHaveCount(0); await expect(page.locator('.detail-title')).toContainText('T0005');
  await page.locator('.maplibregl-canvas').focus(); await page.keyboard.press('Escape'); await expect(page.getByText('Inspect a vehicle', { exact: true })).toBeVisible();
  const fullscreen = page.getByRole('button', { name: 'Fullscreen map', exact: true });
  if (await fullscreen.isEnabled()) {
    await fullscreen.click(); await expect(slider).toBeVisible();
    await page.getByRole('button', { name: 'Open commands', exact: true }).click(); await expect(command).toBeFocused(); await page.keyboard.press('Escape');
    await page.getByRole('button', { name: 'Exit fullscreen map', exact: true }).click();
  }
  await page.setViewportSize({ width: 1920, height: 1080 });
  await expect.poll(async () => (await page.locator('.map-region').boundingBox())!.width).toBeGreaterThan(1000);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('atlas-polish-1080.png') });
  await page.setViewportSize({ width: 1366, height: 768 });
  await expect(slider).toBeInViewport();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('atlas-polish-laptop.png') });
  expect(errors).toEqual([]);
});
test('shortcuts do not edit playback while typing', async ({ page }, testInfo) => {
  await page.goto('/'); await expect(page.locator('.vehicle-marker')).toHaveCount(16);
  const slider = page.getByRole('slider', { name: 'Simulated time', exact: true }); const initial = await slider.inputValue();
  const search = page.getByRole('textbox', { name: 'Search vehicle tracks' }); await search.fill('F'); await search.press('Space'); await search.press('ArrowRight');
  expect(await slider.inputValue()).toBe(initial); await expect(page.getByRole('button', { name: 'Play', exact: true })).toBeVisible();
});
test('malformed tracks produce an actionable error and retry succeeds', async ({ page }, testInfo) => {
  await page.route('**/mock_data/tracks.csv', route => route.fulfill({ status: 200, body: 'bad,header\ninvalid' }));
  await page.goto('/'); await expect(page.getByRole('status')).toContainText('Malformed tracks.csv');
  await page.unroute('**/mock_data/tracks.csv'); await page.getByRole('button', { name: 'Retry loading' }).click(); await expect(page.locator('.vehicle-marker')).toHaveCount(16);
});
test('missing zones are identified separately', async ({ page }, testInfo) => {
  await page.route('**/mock_data/zones.json', route => route.fulfill({ status: 503, body: 'unavailable' }));
  await page.goto('/'); await expect(page.getByRole('status')).toContainText('zones.json unavailable');
});
