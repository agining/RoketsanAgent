import { afterEach, describe, expect, it, vi } from 'vitest';
import { graphSnapshot } from '../../tests/fixtures/graph-snapshot';
import { api } from './api';
import { validateGraphAnalysis } from './graphAnalysisService';
import { regionFeatures } from '../components/graph/useGraphOverlay';

afterEach(() => vi.unstubAllGlobals());

describe('game graph contract', () => {
  it('accepts the API contract and empty windows', () => {
    expect(validateGraphAnalysis(graphSnapshot)).toEqual(graphSnapshot);
    expect(validateGraphAnalysis({ ...graphSnapshot, regions: [], high_interest_regions: [], region_count: 0, high_interest_region_count: 0 })).toBeTruthy();
  });
  it.each([
    { ...graphSnapshot, global_threat_rate: NaN },
    { ...graphSnapshot, regions: [{ ...graphSnapshot.regions[0], interest_score: 2 }] },
    { ...graphSnapshot, regions: [{ ...graphSnapshot.regions[0], normal_vehicle_count: 100 }] },
    { ...graphSnapshot, regions: [{ ...graphSnapshot.regions[0], score_breakdown: null }] },
  ])('rejects malformed data before mapping', value => {
    expect(() => validateGraphAnalysis(value)).toThrow('/api/graph-analysis');
  });
  it('encodes simulation windows and uses POST for explicit recomputation', async () => {
    const fetch = vi.fn(async () => Response.json(graphSnapshot));
    vi.stubGlobal('fetch', fetch);
    await api.graphAnalysis({ start_time: '10:00', end_time: '12:00' });
    await api.graphRecompute({ start_time: '10:00' });
    const calls = fetch.mock.calls as unknown as Array<[string, RequestInit]>;
    expect(calls[0][0]).toBe('/api/graph-analysis?start_time=10%3A00&end_time=12%3A00');
    expect(calls[1][1].method).toBe('POST');
    expect(JSON.parse(calls[1][1].body as string)).toEqual({ force: true });
  });
  it('maps longitude first and preserves selected-region identity', () => {
    const features = regionFeatures(graphSnapshot.regions, graphSnapshot.regions[0].region_id);
    expect(features.features[0].geometry.coordinates).toEqual([32.853, 39.922]);
    expect(features.features[0].properties?.selected).toBe(true);
    expect(regionFeatures([], null).features).toEqual([]);
  });
});
