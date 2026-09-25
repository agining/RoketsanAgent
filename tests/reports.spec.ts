import { readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';
import type { AnalysisData } from '../src/types/analysis';

const analysis = JSON.parse(readFileSync(new URL('../backend/analysis.json', import.meta.url), 'utf8')) as AnalysisData;
const seconds = (time: string) => {
  const [hour, minute] = time.split(':').map(Number);
  return hour * 3600 + minute * 60;
};
async function seekTimeline(page: import('@playwright/test').Page, time: string) {
  await page.locator('.time-slider').evaluate((node, value) => {
    const input = node as HTMLInputElement;
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
    setter?.call(input, String(value));
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
  }, seconds(time));
}

test('reports preserve backend verdicts and evidence separation', async ({ page }) => {
  const entity = analysis.entities.find(item => item.reports.length > 0)!;
  await page.goto('/');
  await page.getByRole('button', { name: /All Tracks/ }).click();
  const explorer = page.getByRole('article', { name: 'All tracks' });
  await explorer.getByRole('textbox', { name: 'Search analyzed tracks' }).fill(entity.track_id);
  await explorer.getByRole('button', { name: `Open track ${entity.track_id}` }).click();
  const detail = page.getByRole('complementary', { name: 'Vehicle details' });
  await expect(detail.getByText('Current Evidence', { exact: true })).toBeVisible();
  await expect(detail.getByText('Historical Evidence', { exact: true })).toBeVisible();
  await expect(detail.locator('.entity-report-list > article')).toHaveCount(0);
  await expect(detail).toContainText('No field reports available by 12:00');
  await seekTimeline(page, entity.reports.at(-1)!.time);
  await expect(detail.locator('.entity-report-list > article')).toHaveCount(entity.reports.length);
  await expect(detail.locator('.report-verdict').first()).toHaveText(entity.reports[0].verdict);
  await expect(detail).toContainText('not treated as authoritative truth');
});
