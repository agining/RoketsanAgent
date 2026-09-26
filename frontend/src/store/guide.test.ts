import { beforeEach, describe, expect, it } from 'vitest';
import { normalizeGuideSteps } from '../services/guide';
import { useGuideStore } from './guide';

describe('normalizeGuideSteps', () => {
  it('keeps valid steps in order and drops malformed ones and consecutive duplicates', () => {
    expect(normalizeGuideSteps([
      { id: 'sidebar-open', instruction: 'Aç', opens: 'sidebar' },
      { id: 'filter-risk', instruction: 'Seç', opens: null },
      { id: 'filter-risk', instruction: 'tekrar' },
      { id: 'Bad Id!' }, null, 'filter-zone', { instruction: 'kimliksiz' },
      { id: 'filter-zone', instruction: 3, opens: '<script>' },
    ])).toEqual([
      { id: 'sidebar-open', instruction: 'Aç', opens: 'sidebar' },
      { id: 'filter-risk', instruction: 'Seç', opens: null },
      { id: 'filter-zone', instruction: '', opens: null },
    ]);
    expect(normalizeGuideSteps({ steps: [] })).toEqual([]);
  });
});

describe('useGuideStore', () => {
  beforeEach(() => useGuideStore.getState().stop());
  const plan = { steps: [{ id: 'a' }, { id: 'b' }, { id: 'c' }], message: 'Filtreleme', question: 'Filtre nasıl yapılır' };

  it('walks the sequence and ends after the last step', () => {
    expect(useGuideStore.getState().start(plan)).toBe(true);
    expect(useGuideStore.getState()).toMatchObject({ index: 0, message: 'Filtreleme', question: 'Filtre nasıl yapılır' });
    useGuideStore.getState().next();
    useGuideStore.getState().next();
    expect(useGuideStore.getState().index).toBe(2);
    useGuideStore.getState().next();
    expect(useGuideStore.getState().steps).toEqual([]);
  });

  it('ignores a stale advance for a step that is no longer current', () => {
    useGuideStore.getState().start(plan);
    useGuideStore.getState().next(0);
    useGuideStore.getState().next(0);
    expect(useGuideStore.getState().index).toBe(1);
  });

  it('stop clears the sequence and an empty plan does not start one', () => {
    useGuideStore.getState().start(plan);
    useGuideStore.getState().stop();
    expect(useGuideStore.getState().steps).toEqual([]);
    expect(useGuideStore.getState().start({ steps: [], message: 'ilgisiz' })).toBe(false);
    expect(useGuideStore.getState().steps).toEqual([]);
  });
});
