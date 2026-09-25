import { describe, expect, it } from 'vitest';
import type { TrackingData } from '../types/tracking';
import type { AnalysisVehicle } from '../types/analysis';
import { criticalVehiclesAtTime, currentFrameAtTime, zoneSummariesAtTime } from './operation-summary';

const vehicle: AnalysisVehicle = { vehicle_id: 'f1-v0', frame_id: 'f1', capture_time: '12:00', capture_min: 720, source: 'detection', label: 'truck', confidence: .9, lat: 39, lon: 32, zone: 'North', dist_to_base_m: 900, track_id: 'T1', track_match_m: 1, features: { heading_deg: 0, speed_now_mps: 4 }, filtered: false, scenario: 'APPROACH', risk_level: 'KRITIK', risk_reasons: ['Rapid approach.'] };
const data: TrackingData = {
  base: { name: 'Base', lat: 39, lon: 32 }, zones: [{ name: 'North', center: [39, 32] }, { name: 'South', center: [38, 32] }],
  tracks: [{ id: 'T1', points: [{ time: '12:00', lat: 39, lon: 32 }] }],
  analysis: {
    summary: { frames: 1, frame_risk_counts: { DUSUK: 0, ORTA: 0, YUKSEK: 0, KRITIK: 1 }, vehicles: 1, missed_detections_recovered: 0, offframe_tracks: 0, report_verdicts: { celisir: 1 } },
    frames: { f1: { frame_id: 'f1', capture_time: '12:00', zone: 'North', risk_level: 'KRITIK', counts: { DUSUK: 0, ORTA: 0, YUKSEK: 0, KRITIK: 1 }, top_vehicle_id: 'f1-v0', vehicles: [vehicle], reports: [] } },
    reports: [{ report_id: 'R1', time: '11:55', source: 'official', text: 'Normal traffic.', verdict: 'celisir', report_type: 'NORMAL', summary: 'Conflict.', matched_vehicle_id: 'f1-v0', matched_track_id: 'T1', zone: 'North', related_frames: ['f1'], checks: {}, injection_detected: false, parsed: { coord: null, zone: 'North', types: [], type_word: null, count: null, color: null, claims_stationary: false, claims_moving: false, claims_fast: false, direction_deg: null, toward_base: false, claims_normal: true, zone_traffic_normal: false, friendly_claim: false, friendly_confirmed_wording: false, stale: false, exercise: false, injection: false, injection_span: null } }],
  },
};

describe('operation summary helpers', () => {
  it('selects only a frame close to the playback cursor', () => {
    expect(currentFrameAtTime(data.analysis, 721 * 60)?.frame_id).toBe('f1');
    expect(currentFrameAtTime(data.analysis, 730 * 60)).toBeNull();
  });
  it('reveals critical vehicles only after their analysis time', () => {
    expect(criticalVehiclesAtTime(data, 719 * 60)).toEqual([]);
    expect(criticalVehiclesAtTime(data, 720 * 60)[0]).toMatchObject({ trackId: 'T1', type: 'truck', risk: 'KRITIK' });
  });
  it('builds playback-aware zone counts and report conflicts', () => {
    expect(zoneSummariesAtTime(data, 719 * 60)[0]).toMatchObject({ vehicles: 0, conflicts: 1 });
    expect(zoneSummariesAtTime(data, 720 * 60)[0]).toMatchObject({ vehicles: 1, elevated: 1, untracked: 0, conflicts: 1 });
  });
});
