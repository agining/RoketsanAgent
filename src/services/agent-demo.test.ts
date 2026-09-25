import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { alertsAtTime, buildSitrep } from './agent-demo';
import { parseAnalysisData } from './analysis';
import { parseTracksCsv, parseZones } from './tracking';

const analysis = parseAnalysisData(JSON.parse(readFileSync(new URL('../../mock_data/analysis.json', import.meta.url), 'utf8')));
const tracks = parseTracksCsv(readFileSync(new URL('../../mock_data/tracks.csv', import.meta.url), 'utf8'));
const refs = parseZones(JSON.parse(readFileSync(new URL('../../mock_data/zones.json', import.meta.url), 'utf8')));
const data = { analysis, tracks, ...refs };

describe('final agent demo data', () => {
  it('does not expose future alerts and includes alerts present in mock data', () => {
    expect(alertsAtTime(data, 10 * 3600).some(alert => alert.time > '10:00')).toBe(false);
    const alerts = alertsAtTime(data, 12 * 3600 + 30 * 60);
    expect(alerts.some(alert => alert.kind === 'untracked' && alert.risk === 'ORTA')).toBe(true);
    expect(alerts.some(alert => alert.kind === 'contradictions')).toBe(true);
  });
  it('builds a deterministic Turkish SITREP without an API call', () => {
    const sitrep = buildSitrep(data, 12 * 3600 + 5 * 60);
    expect(sitrep).toContain('SITREP 12:05'); expect(sitrep).toContain('yüksek/kritik');
  });
});
