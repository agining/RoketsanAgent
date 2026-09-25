import { describe, expect, it } from 'vitest';
import type { AnalysisData, AnalysisReport } from '../types/analysis';
import { reportMatchesFilters, reportsAtTime } from './reports';

const parsed: AnalysisReport['parsed'] = { coord: [39, 32], zone: null, types: ['car'], type_word: 'car', count: 1, color: null, claims_stationary: false, claims_moving: true, claims_fast: false, direction_deg: null, toward_base: false, claims_normal: false, zone_traffic_normal: false, friendly_claim: false, friendly_confirmed_wording: false, stale: false, exercise: false, injection: false, injection_span: null };
const report = (overrides: Partial<AnalysisReport> = {}): AnalysisReport => ({ report_id: 'R1', time: '12:00', source: 'official', text: 'Vehicle observed.', verdict: 'destekler', report_type: 'OBSERVATION', summary: 'Supported.', matched_vehicle_id: 'v1', matched_track_id: 'T1', zone: 'North', related_frames: ['f1'], checks: {}, injection_detected: false, parsed, ...overrides });
const analysis: AnalysisData = { frames: {}, reports: [report(), report({ report_id: 'R2', time: '12:10', verdict: 'celisir' }), report({ report_id: 'R3', time: '12:15', source: 'third_party', verdict: 'manipulasyon', injection_detected: true })], summary: { frames: 0, frame_risk_counts: { DUSUK: 0, ORTA: 0, YUKSEK: 0, KRITIK: 0 }, vehicles: 0, missed_detections_recovered: 0, offframe_tracks: 0, report_verdicts: {} } };

describe('report filtering', () => {
  it('never exposes reports after the playback cursor', () => {
    expect(reportsAtTime(analysis, 12 * 3600 + 5 * 60).map(item => item.report_id)).toEqual(['R1']);
  });
  it('filters verdict groups and sources', () => {
    expect(reportsAtTime(analysis, 13 * 3600, { mode: 'contradictions', source: 'all' }).map(item => item.report_id)).toEqual(['R2']);
    expect(reportsAtTime(analysis, 13 * 3600, { mode: 'manipulation', source: 'third_party' }).map(item => item.report_id)).toEqual(['R3']);
    expect(reportMatchesFilters(report(), { mode: 'supporting', source: 'official' })).toBe(true);
  });
});
