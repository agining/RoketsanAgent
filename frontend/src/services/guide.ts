import type { ApiGuideStep } from '../types/api';

/**
 * UI guide helpers. The API (POST /api/ui-guide) turns a spoken "how do I…" question into an ordered list of
 * element IDs from app/ui_guide.md; every such element carries `data-guide="<id>"` in the markup.
 */
export type GuideStep = ApiGuideStep;

const GUIDE_ID = /^[a-z0-9-]+$/;

/** Defensive normalisation of the API's steps: drops malformed entries and consecutive duplicates. */
export function normalizeGuideSteps(raw: unknown): GuideStep[] {
  if (!Array.isArray(raw)) return [];
  const steps: GuideStep[] = [];
  for (const item of raw) {
    if (!item || typeof item !== 'object') continue;
    const { id, instruction, opens } = item as Record<string, unknown>;
    if (typeof id !== 'string' || !GUIDE_ID.test(id) || steps.at(-1)?.id === id) continue;
    steps.push({
      id,
      instruction: typeof instruction === 'string' ? instruction : '',
      opens: typeof opens === 'string' && GUIDE_ID.test(opens) ? opens : null,
    });
  }
  return steps;
}

/** The element for a guide ID, or null when it is not rendered or has no size (hidden by CSS / collapsed). */
export function findGuideTarget(id: string): HTMLElement | null {
  const element = document.querySelector<HTMLElement>(`[data-guide="${id}"]`);
  if (!element) return null;
  const rect = element.getBoundingClientRect();
  return rect.width > 0 && rect.height > 0 ? element : null;
}
