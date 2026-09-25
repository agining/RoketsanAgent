import { describe, expect, it } from 'vitest';
import type { AnalysisData, AnalysisEntity } from '../types/analysis';
import { analysisPlaybackBounds, positionAtTime, reportsAtTime, reportsUntil, timelineEvents, trackTrail } from './analysis-playback';

const entity = {
  track_id: 'T0001',
  position_history: [
    { time: '12:00', lat: 0, lon: 0, zone: 'A', distance_to_base_m: 1000 },
    { time: '12:05', lat: 0, lon: 1, zone: 'A', distance_to_base_m: 800 },
    { time: '12:10', lat: 1, lon: 1, zone: 'B', distance_to_base_m: 600 },
  ],
  movement_history: [
    { time: '12:05', state: 'APPROACHING_BASE', speed_mps: 4, closing_speed_mps: 3, eta_min: 10, distance_to_base_m: 800 },
  ],
  behavior_history: [
    { time: '12:10', behavior: 'LOITERING', path_efficiency: 0.3, heading_change_total_deg: 180, flags: ['LOITERING'] },
  ],
  reports: [
    { time: '12:05', source: 'official', text: 'near gate', report_type: 'sighting', vehicle_type: 'car', matched_track_id: 'T0001', match_distance_m: 12, verdict: 'SUPPORTED', supported_checks: 1, contradicted_checks: 0, checks: [], reasons: [] },
    { time: '12:20', source: 'third_party', text: 'future report', report_type: 'sighting', vehicle_type: 'car', matched_track_id: 'T0001', match_distance_m: 30, verdict: 'UNVERIFIED', supported_checks: 0, contradicted_checks: 0, checks: [], reasons: [] },
  ],
} as unknown as AnalysisEntity;

const analysis = { entities: [entity] } as unknown as AnalysisData;

describe('analysis playback projections', () => {
  it('uses real position history, interpolates only between observed coordinates and marks stale after last point', () => {
    expect(analysisPlaybackBounds(analysis)).toEqual({ minTime: 43200, maxTime: 43800 });
    expect(positionAtTime(entity, 43199)).toBeNull();
    expect(positionAtTime(entity, 43350)?.lon).toBeCloseTo(0.5);
    expect(positionAtTime(entity, 43900)?.stale).toBe(true);
    expect(positionAtTime(entity, 43900)?.lat).toBe(1);
  });

  it('builds elapsed trails and avoids future report leakage', () => {
    expect(trackTrail(entity, 43350)).toEqual([[0, 0], [0.5, 0]]);
    expect(reportsUntil(entity, 43500)).toHaveLength(1);
    expect(reportsUntil(entity, 43500)[0].text).toBe('near gate');
    expect(reportsAtTime(entity, 43500)).toHaveLength(1);
  });

  it('exposes movement, behavior and report events for timeline ticks', () => {
    expect(timelineEvents(analysis).map(event => event.type)).toEqual(['APPROACHING_BASE', 'REPORT', 'LOITERING', 'REPORT']);
  });
});
