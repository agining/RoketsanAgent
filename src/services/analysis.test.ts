import { describe, expect, it } from 'vitest';
import { analysisForTrack, buildAnalysisIndex, parseAnalysisData, untrackedAtTime, vehicleType } from './analysis';
import type { AnalysisData, AnalysisVehicle } from '../types/analysis';

const vehicle = (overrides: Partial<AnalysisVehicle> = {}): AnalysisVehicle => ({
  vehicle_id: 'frame-1-v0', frame_id: 'frame-1', capture_time: '12:00', capture_min: 720,
  source: 'detection', label: 'car', confidence: .9, lat: 39, lon: 32, zone: 'North',
  dist_to_base_m: 1000, track_id: 'T1', track_match_m: 2, features: { heading_deg: 45, speed_now_mps: 5 },
  filtered: false, scenario: 'NORMAL', risk_level: 'DUSUK', ...overrides,
});
const summary: AnalysisData['summary'] = { frames: 1, frame_risk_counts: { DUSUK: 1, ORTA: 0, YUKSEK: 0, KRITIK: 0 }, vehicles: 1, missed_detections_recovered: 0, offframe_tracks: 0, report_verdicts: {} };
const data = (...vehicles: AnalysisVehicle[]): AnalysisData => ({ summary, frames: { 'frame-1': { frame_id: 'frame-1', capture_time: '12:00', zone: 'North', risk_level: 'DUSUK', counts: { DUSUK: 1, ORTA: 0, YUKSEK: 0, KRITIK: 0 }, top_vehicle_id: vehicles[0]?.vehicle_id ?? null, vehicles, reports: [] } } });

describe('analysis helpers', () => {
  it('indexes tracked vehicles separately from untracked detections', () => {
    const index = buildAnalysisIndex(data(vehicle(), vehicle({ vehicle_id: 'u1', track_id: null })));
    expect(index.byTrackId.get('T1')).toHaveLength(1); expect(index.untracked.map(item => item.vehicle_id)).toEqual(['u1']);
  });
  it('selects the analysis snapshot nearest to playback and limits untracked snapshots by time', () => {
    const index = buildAnalysisIndex(data(vehicle(), vehicle({ vehicle_id: 'later', capture_min: 730 }), vehicle({ vehicle_id: 'u1', track_id: null })));
    expect(analysisForTrack(index, 'T1', 729 * 60)?.vehicle_id).toBe('frame-1-v0');
    expect(analysisForTrack(index, 'T1', 719 * 60)).toBeNull();
    expect(untrackedAtTime(index, 721 * 60)).toHaveLength(1); expect(untrackedAtTime(index, 724 * 60)).toHaveLength(0);
  });
  it('uses the generic type for track-only records and rejects malformed frames', () => {
    expect(vehicleType(vehicle({ source: 'track_only', label: null }))).toBe('unknown');
    expect(() => parseAnalysisData({ summary, frames: { bad: { frame_id: 'other', vehicles: [] } } })).toThrow('bad');
  });
  it('normalizes off-frame risk records onto their matching tracks', () => {
    const analysis: AnalysisData = { ...data(), offframe_tracks: { T2: { track_id: 'T2', scenario: 'LOITER', risk_level: 'YUKSEK', last_time: '12:40', lat: 39, lon: 32, zone: 'North', features: { heading_deg: 120, speed_now_mps: 2, dist_now_m: 1900 } } } };
    const match = analysisForTrack(buildAnalysisIndex(analysis), 'T2', 760 * 60);
    expect(match).toMatchObject({ source: 'offframe', label: null, risk_level: 'YUKSEK', capture_min: 760 });
    expect(vehicleType(match)).toBe('unknown');
  });
});
