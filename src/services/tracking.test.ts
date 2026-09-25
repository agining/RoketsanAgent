import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { parseTracksCsv, parseZones, validateDatasetConsistency } from './tracking';
import { parseAnalysisData } from './analysis';
import { routeFeatures, trackingBounds } from './map-data';
const header = 'track_id,time,lat,lon\n';
describe('tracking data', () => {
  it('groups interleaved rows and preserves first point and source order', () => {
    const tracks = parseTracksCsv('\uFEFF' + header + 'T1,23:55,39,32\r\nT2,12:00,40,33\r\nT1,00:00,39.1,32.1\r\n');
    expect(tracks).toEqual([{ id: 'T1', points: [{ time: '23:55', lat: 39, lon: 32 }, { time: '00:00', lat: 39.1, lon: 32.1 }] }, { id: 'T2', points: [{ time: '12:00', lat: 40, lon: 33 }] }]);
    expect(routeFeatures(tracks).features[0].geometry.coordinates).toEqual([[32, 39], [32.1, 39.1]]);
    expect(routeFeatures(tracks).features).toHaveLength(1);
  });
  it.each(['T1,25:00,39,32', 'T1,12:00,,32', 'T1,12:00,91,32', 'T1,12:00,39,NaN', ',12:00,39,32'])('rejects invalid row %s', row => {
    expect(() => parseTracksCsv(header + row)).toThrow('row 2');
  });
  it('rejects empty datasets, bad headers, and invalid zones', () => {
    expect(() => parseTracksCsv(header)).toThrow('No vehicle');
    expect(() => parseTracksCsv('id,time,lat,lon')).toThrow('header');
    expect(() => parseZones({ base: { name: 'base', lat: 39, lon: 32 }, zones: [{ name: 'zone', center: [32, 190] }] })).toThrow();
  });
  it('loads all supplied points and includes tracks, zones, and base in bounds', () => {
    const csv = readFileSync(new URL('../../mock_data/tracks.csv', import.meta.url), 'utf8');
    const data = { tracks: parseTracksCsv(csv), ...parseZones(JSON.parse(readFileSync(new URL('../../mock_data/zones.json', import.meta.url), 'utf8'))) };
    const analysis = parseAnalysisData(JSON.parse(readFileSync(new URL('../../mock_data/analysis.json', import.meta.url), 'utf8')));
    expect(data.tracks.reduce((count, track) => count + track.points.length, 0)).toBe(400);
    expect(data.tracks).toHaveLength(16);
    expect(data.zones).toHaveLength(8);
    expect(() => validateDatasetConsistency(data.tracks, analysis)).not.toThrow();
    const bounds = trackingBounds(data);
    for (const track of data.tracks) for (const point of track.points) {
      expect(point.lon).toBeGreaterThanOrEqual(bounds[0][0]); expect(point.lon).toBeLessThanOrEqual(bounds[1][0]);
      expect(point.lat).toBeGreaterThanOrEqual(bounds[0][1]); expect(point.lat).toBeLessThanOrEqual(bounds[1][1]);
    }
  });
  it('rejects analysis generated for a different track set', () => {
    const analysis = parseAnalysisData(JSON.parse(readFileSync(new URL('../../mock_data/analysis.json', import.meta.url), 'utf8')));
    expect(() => validateDatasetConsistency([{ id: 'NOT_IN_ANALYSIS', points: [] }], analysis)).toThrow('out of sync');
  });
});
