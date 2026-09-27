import { expect, test } from '@playwright/test';
import { mockApi } from './support/mock-api';

test('analyst decides a pending review and can undo it', async ({ page }) => {
  const { calls } = await mockApi(page);
  await page.goto('/');
  await page.getByRole('button', { name: 'Ayarları aç', exact: true }).click();
  await expect(page.getByRole('switch', { name: /Son söz insanda/ })).toHaveAttribute('aria-checked', 'true');
  await page.getByRole('button', { name: 'Ayarlar panelini kapat', exact: true }).click();
  await page.getByRole('button', { name: /Analist Onayı/ }).click();
  const panel = page.getByRole('region', { name: 'Analist onayı' });
  const card = panel.getByRole('article', { name: 'img_006574_v0 analist kararı' });
  await expect(card).toContainText('Analist onayı bekliyor');
  await expect(card).toContainText('Resmi rapor aracın dost unsur olduğunu belirtiyor.');
  await panel.getByRole('textbox', { name: 'Analist adı' }).fill('Buğra');
  await card.getByRole('radio', { name: 'Orta' }).click();
  await card.getByRole('textbox', { name: 'Analist notu' }).fill('Dost teyidi yeterli');
  await card.getByRole('button', { name: 'Kararı kaydet' }).click();
  await expect(panel.locator('.review-decided')).toContainText('Analist kararı: Orta · Buğra');
  expect(calls.find(call => call.method === 'POST' && call.path === '/api/reviews/img_006574_v0')?.body).toEqual({ level: 'ORTA', analyst: 'Buğra', note: 'Dost teyidi yeterli' });
  await panel.getByRole('button', { name: 'Geri al' }).click();
  await expect(panel.locator('.review-decided')).toHaveCount(0);
  expect(calls.some(call => call.method === 'DELETE' && call.path === '/api/reviews/img_006574_v0')).toBe(true);
});

test('human review switch calls PUT /api/settings', async ({ page }) => {
  const { calls } = await mockApi(page);
  await page.goto('/');
  await page.getByRole('button', { name: 'Ayarları aç', exact: true }).click();
  const toggle = page.getByRole('switch', { name: /Son söz insanda/ });
  await toggle.click();
  await expect(toggle).toHaveAttribute('aria-checked', 'false');
  expect(calls.find(call => call.method === 'PUT')?.body).toEqual({ human_review: false });
  await page.getByRole('button', { name: 'Ayarlar panelini kapat', exact: true }).click();
  await page.getByRole('button', { name: /Analist Onayı/ }).click();
  await expect(page.getByRole('region', { name: 'Analist onayı' })).toContainText('"Son söz insanda" kapalı');
});

test('frame assessment is requested from the API and shown in the detail', async ({ page }) => {
  const { calls } = await mockApi(page);
  await page.goto('/');
  await page.getByRole('button', { name: /Öncelikli Araçlar/ }).click();
  await page.getByRole('region', { name: 'Öncelikli araç kayıtları' }).locator(':scope > div > button').first().click();
  const detail = page.getByRole('complementary', { name: 'Araç detayları' });
  await detail.getByRole('button', { name: /Ajan Değerlendirmesi/ }).click();
  await detail.getByRole('button', { name: 'Kareyi ajanla değerlendir' }).evaluate(element => element.scrollIntoView({ block: 'center' }));
  await detail.getByRole('button', { name: 'Kareyi ajanla değerlendir' }).click();
  await expect(detail).toContainText('img_006140 başlık');
  await expect(detail).toContainText('Sürekli izle.');
  expect(calls.some(call => call.method === 'POST' && call.path === '/api/frames/img_006140/assess')).toBe(true);
});

test('agent chat posts to /api/chat with the selected frame as context', async ({ page }) => {
  const { calls } = await mockApi(page);
  await page.goto('/');
  await page.getByRole('button', { name: /Tüm İz Kayıtları/ }).click();
  await page.getByRole('button', { name: 'T0106 iz detayını aç' }).click();
  await page.getByRole('button', { name: 'Ajan', exact: true }).click();
  await page.getByRole('textbox', { name: 'Ajan mesajı' }).fill('En kritik araç hangisi?');
  await page.getByRole('button', { name: 'Ajan mesajını gönder' }).click();
  await expect(page.locator('.chat-message.agent')).toContainText('En kritik araç T0106. (img_006140)');
  expect(calls.find(call => call.path === '/api/chat')?.body).toMatchObject({ message: 'En kritik araç hangisi?', frame_id: 'img_006140' });
});
