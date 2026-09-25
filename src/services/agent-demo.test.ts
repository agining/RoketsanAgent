import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { alertsAtTime, buildSitrep } from './agent-demo';
import { parseAnalysis } from './analysisService';
import { parseTracksCsv } from './tracking';

const analysis = parseAnalysis(JSON.parse(readFileSync(new URL('../../backend/analysis.json', import.meta.url), 'utf8')));
const tracks = parseTracksCsv(readFileSync(new URL('../../mock_data/tracks.csv', import.meta.url), 'utf8'));
const data = { analysis, tracks, base: analysis.base, zones: analysis.zones };

describe('agent data projections', () => {
  it('does not expose future alerts', () => {
    expect(alertsAtTime(data, 12 * 3600).some(alert => alert.time > '12:00')).toBe(false);
    expect(alertsAtTime(data, 14 * 3600).some(alert => alert.kind === 'untracked')).toBe(true);
  });
  it('builds a deterministic local SITREP', () => {
    expect(buildSitrep(data, 13 * 3600)).toContain('SITREP 13:00');
  });
});
