import { expect, test, type Page } from '@playwright/test';
import { mockApi } from './support/mock-api';

// Chromium's fake microphone lets the real recording → WAV → transcribe path run without a device.
test.use({
  permissions: ['microphone'],
  launchOptions: { args: ['--enable-unsafe-swiftshader', '--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] },
});

async function mockVoice(page: Page, transcript: string, plan: { message: string; actions: { action: string; params: Record<string, unknown> }[] }) {
  const commands: Array<{ command: string; context: any }> = [];
  let transcribed: { type: string; bytes: number } | null = null;
  await page.route('**/api/asr/status', route => route.fulfill({ json: { loaded: true, loading: false, model: 'openai/whisper-small', language: 'turkish', device: 'cpu' } }));
  await page.route('**/api/asr/transcribe', route => {
    transcribed = { type: route.request().headers()['content-type'], bytes: route.request().postDataBuffer()?.length ?? 0 };
    return route.fulfill({ json: { text: transcript, duration_s: 1, elapsed_s: 0.1 } });
  });
  await page.route('**/api/ui-command', route => {
    commands.push(route.request().postDataJSON());
    return route.fulfill({ json: { command: transcript, dropped: [], ...plan } });
  });
  return { commands, transcribed: () => transcribed };
}

async function speak(page: Page) {
  const button = page.getByRole('button', { name: 'Sesli komut ver' });
  await button.click();
  await expect(page.getByText('Dinleniyor', { exact: false })).toBeVisible();
  await page.waitForTimeout(600);
  await page.getByRole('button', { name: 'Sesli komutu bitir' }).click();
}

test('"Sadece otobüsleri göster" filters the map to buses through the existing filters', async ({ page }) => {
  await mockApi(page);
  const voice = await mockVoice(page, 'Sadece otobüsleri göster', {
    message: 'Yalnızca otobüsler gösteriliyor.',
    actions: [{ action: 'clear_filters', params: {} }, { action: 'set_filters', params: { vehicle_class: 'bus' } }, { action: 'open_panel', params: { panel: 'sidebar' } }],
  });
  await page.goto('/');
  await page.getByLabel('Risk filtresi').selectOption('HIGH');

  await speak(page);

  await expect(page.getByText('Yalnızca otobüsler gösteriliyor.')).toBeVisible();
  await expect(page.getByLabel('Araç filtresi', { exact: true })).toHaveValue('bus');
  await expect(page.getByLabel('Harita araç filtresi')).toHaveValue('bus');
  await expect(page.getByLabel('Risk filtresi', { exact: true })).toHaveValue('ALL');
  const shortlist = page.locator('.map-track-shortlist button');
  await expect(shortlist.first()).toBeVisible();
  for (const text of await shortlist.allTextContents()) expect(text).toContain('Otobüs');

  expect(voice.transcribed()).toMatchObject({ type: 'audio/wav' });
  expect(voice.transcribed()!.bytes).toBeGreaterThan(44);
  const [sent] = voice.commands;
  expect(sent.command).toBe('Sadece otobüsleri göster');
  expect(sent.context.options.vehicle_class).toContainEqual({ value: 'bus', label: 'Otobüs' });
  expect(sent.context.state.filters.risk).toBe('HIGH');
});

test('voice command opens panels, changes settings and reports actions it could not apply', async ({ page }) => {
  await mockApi(page);
  await mockVoice(page, 'Öncelikli araçları aç, açık temaya geç ve tankları göster', {
    message: 'Paneller açıldı.',
    actions: [
      { action: 'open_panel', params: { panel: 'priority' } },
      { action: 'set_theme', params: { mode: 'light' } },
      { action: 'set_filters', params: { vehicle_class: 'tank' } },
    ],
  });
  await page.goto('/');

  await speak(page);

  await expect(page.getByLabel('Öncelikli araç kayıtları')).toBeVisible();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await expect(page.getByText('set_filters: Araç tipi geçersiz: tank.')).toBeVisible();
});

test('agent chat mic dictates into the message box', async ({ page }) => {
  await mockApi(page);
  await mockVoice(page, 'En kritik araç hangisi', { message: '', actions: [] });
  await page.goto('/');
  await page.getByRole('button', { name: /^Ajan/ }).click();

  await page.getByRole('button', { name: 'Sesle yaz' }).click();
  await expect(page.getByText('Dinleniyor', { exact: false })).toBeVisible();
  await page.waitForTimeout(600);
  await page.getByRole('button', { name: 'Ses kaydını durdur' }).click();

  await expect(page.getByRole('textbox', { name: 'Ajan mesajı' })).toHaveValue('En kritik araç hangisi');
});
