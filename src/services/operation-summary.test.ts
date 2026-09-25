import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { parseAnalysis } from './analysisService';
import { parseTracksCsv } from './tracking';
import { criticalVehiclesAtTime, currentFrameAtTime, zoneSummariesAtTime } from './operation-summary';

const analysis = parseAnalysis(JSON.parse(readFileSync(new URL('../../backend/analysis.json', import.meta.url), 'utf8')));
const tracks = parseTracksCsv(readFileSync(new URL('../../mock_data/tracks.csv', import.meta.url), 'utf8'));
const data = { analysis, tracks, base: analysis.base, zones: analysis.zones };

describe('operation summary projections', () => {
  it('builds snapshots only near real history timestamps', () => {
    expect(currentFrameAtTime(analysis, 13 * 3600)?.capture_time).toBe('13:00');
    expect(currentFrameAtTime(analysis, 13 * 3600 + 10 * 60)).toBeNull();
  });
  it('uses current backend risk assessments for known entities', () => {
    expect(criticalVehiclesAtTime(data, 12 * 3600)).toEqual([]);
    expect(criticalVehiclesAtTime(data, 13 * 3600).some(item => item.risk === 'HIGH')).toBe(true);
  });
  it('creates one row per backend zone', () => {
    expect(zoneSummariesAtTime(data, 14 * 3600)).toHaveLength(analysis.zones.length);
  });
});
