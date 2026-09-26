import { expect, test, type Page } from '@playwright/test';
import { mockApi } from './support/mock-api';

// Chromium's fake microphone lets the real recording → WAV → transcribe path run without a device.
test.use({
  permissions: ['microphone'],
  launchOptions: { args: ['--enable-unsafe-swiftshader', '--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] },
});

const plan = {
  question: 'Filtre nasıl yapılır',
  message: 'Harita panelindeki filtrelerle izleri daraltabilirsiniz.',
  steps: [
    { id: 'sidebar-open', instruction: 'Harita panelini açın.', opens: 'sidebar' },
    { id: 'filter-risk', instruction: 'Risk seviyesini seçin.', opens: null },
    { id: 'sidebar-track-list', instruction: 'Listeden bir iz seçin.', opens: null },
    { id: 'detail-watch', instruction: 'İzi izleme listesine alın.', opens: null },
  ],
  dropped: [],
};

async function mockGuide(page: Page) {
  const asked: string[] = [];
  let transcribed: { type: string; bytes: number } | null = null;
  await page.route('**/api/asr/status', route => route.fulfill({ json: { loaded: true, loading: false, model: 'openai/whisper-small', language: 'turkish', device: 'cpu' } }));
  await page.route('**/api/asr/transcribe', route => {
    transcribed = { type: route.request().headers()['content-type'], bytes: route.request().postDataBuffer()?.length ?? 0 };
    return route.fulfill({ json: { text: 'Filtre nasıl yapılır', duration_s: 1, elapsed_s: 0.1 } });
  });
  await page.route('**/api/ui-guide', route => { asked.push(route.request().postDataJSON().question); return route.fulfill({ json: plan }); });
  return { asked, transcribed: () => transcribed };
}

async function askByVoice(page: Page) {
  const button = page.locator('[data-guide="topbar-voice-guide"]');
  await button.click();
  await expect(page.getByText('Dinleniyor', { exact: false })).toBeVisible();
  await page.waitForTimeout(600);
  await button.click();
}

async function expectRingAround(page: Page, id: string) {
  const ring = page.locator('.guide-ring');
  await expect(ring).toBeVisible();
  await expect.poll(async () => {
    const [a, b] = await Promise.all([ring.boundingBox(), page.locator(`[data-guide="${id}"]`).first().boundingBox()]);
    return a && b ? Math.abs(a.x - (b.x - 4)) < 2 && Math.abs(a.width - (b.width + 8)) < 2 : false;
  }).toBe(true);
}

test('voice question highlights the sequence step by step and skips openers that are already open', async ({ page }) => {
  await page.setViewportSize({ width: 1400, height: 900 });
  await mockApi(page);
  const guide = await mockGuide(page);
  await page.goto('/');
  await expect(page.locator('[data-guide="sidebar"]')).toBeVisible();

  await askByVoice(page);
  const tip = page.getByRole('dialog', { name: 'Arayüz yardımı' });
  // Sidebar is already open, so step 1 ("open the sidebar") is skipped.
  await expect(tip).toContainText('ADIM 2 / 4');
  await expect(tip).toContainText('Risk seviyesini seçin.');
  await expect(tip).toContainText(plan.message);
  expect(guide.asked).toEqual(['Filtre nasıl yapılır']);
  expect(guide.transcribed()).toMatchObject({ type: 'audio/wav' });
  expect(guide.transcribed()!.bytes).toBeGreaterThan(44);
  await expectRingAround(page, 'filter-risk');

  await page.locator('[data-guide="filter-risk"] select').selectOption('CRITICAL');
  await expect(tip).toContainText('ADIM 3 / 4');
  await expectRingAround(page, 'sidebar-track-list');

  // Clicking a track opens the detail drawer; the next step waits for its element to render.
  await page.locator('[data-guide="sidebar-track-list"] button').first().click();
  await expect(tip).toContainText('ADIM 4 / 4');
  await expect(tip).toContainText('İzi izleme listesine alın.');
  await expect(tip).not.toContainText(plan.message);
  await expectRingAround(page, 'detail-watch');

  await page.locator('[data-guide="detail-watch"]').click();
  await expect(tip).toBeHidden();
  await expect(page.locator('.guide-ring')).toHaveCount(0);
});

test('the cross icon ends the sequence; a new question is needed for another one', async ({ page }) => {
  await page.setViewportSize({ width: 1400, height: 900 });
  await mockApi(page);
  const guide = await mockGuide(page);
  await page.goto('/');
  await page.getByRole('button', { name: 'Harita panelini daralt' }).click();

  await askByVoice(page);
  const tip = page.getByRole('dialog', { name: 'Arayüz yardımı' });
  // Sidebar is closed now, so the opener step is shown first.
  await expect(tip).toContainText('ADIM 1 / 4');
  await expectRingAround(page, 'sidebar-open');

  await tip.getByRole('button', { name: 'Yardımı kapat' }).click();
  await expect(tip).toBeHidden();
  await expect(page.locator('.guide-ring')).toHaveCount(0);
  // Clicking the formerly highlighted element no longer does anything guide-related.
  await page.locator('[data-guide="sidebar-open"]').click();
  await expect(tip).toBeHidden();

  await askByVoice(page);
  await expect(tip).toContainText('ADIM 2 / 4');
  expect(guide.asked).toHaveLength(2);
});
