import { afterEach, describe, expect, it, vi } from 'vitest';
import snapshot from '../../tests/fixtures/api-snapshot.json';
import { buildAnalysis, fetchRawAnalysis, type RawAnalysis } from './analysisService';

const raw = snapshot as unknown as RawAnalysis & { tracks: Record<string, unknown> };
const clone = () => structuredClone(raw) as RawAnalysis;

describe('buildAnalysis', () => {
  const analysis = buildAnalysis(clone());

  it('creates one entity per API track and joins the frame vehicle linked to it', () => {
    expect(analysis.entities).toHaveLength(raw.trackingData.tracks.length);
    const critical = analysis.entities.find(entity => entity.track_id === 'T0106')!;
    expect(critical.vehicle?.vehicle_id).toBe('img_006140_v0');
    expect(critical.risk_level).toBe('CRITICAL');
    expect(critical.scenario).toBe('DIRECT_FAST_APPROACH');
    expect(critical.observed_at).toBe(critical.vehicle?.capture_time);
    expect(critical.features?.eta_min).toBeTypeOf('number');
    expect(critical.reports.map(report => report.report_id)).toContain('R009');
  });

  it('uses the API off-frame risk for tracks no frame vehicle is linked to', () => {
    const offframe = analysis.entities.find(entity => entity.track_id === 'T0054')!;
    expect(offframe.source).toBe('offframe');
    expect(offframe.vehicle).toBeNull();
    expect(offframe.risk_level).toBe('HIGH');
    expect(offframe.observed_at).toBe(offframe.offframe?.last_time);
  });

  it('keeps final level, engine level and decision status from the API', () => {
    const pending = analysis.entities.find(entity => entity.track_id === 'T0093')!;
    expect(pending.decision_status).toBe('onay_bekliyor');
    expect(pending.vehicle?.decision?.llm_level).toBe('ORTA');
    expect(pending.engine_risk_level).toBe('HIGH');
    expect(analysis.human_review).toBe(true);
    expect(analysis.reviews.items).toHaveLength(1);
  });

  it('lists frame detections without a track as untracked, including filtered ones', () => {
    const expected = raw.frames.flatMap(frame => frame.vehicles).filter(vehicle => vehicle.track_id === null);
    expect(analysis.untracked.map(item => item.vehicle_id).sort()).toEqual(expected.map(item => item.vehicle_id).sort());
    expect(analysis.untracked.some(item => item.filtered)).toBe(true);
    expect(analysis.untracked.find(item => item.vehicle_id === 'img_005788_v4')?.risk_level).toBe('MEDIUM');
  });

  it('maps summary, alerts and timestamps without recomputing them', () => {
    expect(analysis.generated_at).toBe(new Date(raw.summary.generated_at * 1000).toISOString());
    expect(analysis.summary.frame_risk_counts.CRITICAL).toBe(raw.summary.frame_risk_counts.KRITIK);
    expect(analysis.alerts).toHaveLength(raw.alerts.length);
    expect(analysis.alerts[0].risk_level).toBe('CRITICAL');
    expect(analysis.frames.map(frame => frame.capture_time)).toEqual([...analysis.frames.map(frame => frame.capture_time)].sort());
  });

  it('rejects payloads that break the API contract with the endpoint name', () => {
    const broken = clone(); (broken.trackingData as unknown as { zones: unknown }).zones = [{ name: 'x' }];
    expect(() => buildAnalysis(broken)).toThrow('/api/tracking-data');
    const noSummary = clone(); (noSummary as unknown as { summary: unknown }).summary = {};
    expect(() => buildAnalysis(noSummary)).toThrow('/api/summary');
  });
});

describe('fetchRawAnalysis', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('reads everything from /api and fetches only unlinked tracks individually', async () => {
    const calls: string[] = [];
    const frameList = raw.frames.map(frame => ({ frame_id: frame.frame_id }));
    vi.stubGlobal('fetch', vi.fn(async (input: string) => {
      calls.push(input);
      const path = input.split('?')[0];
      const body = path === '/api/summary' ? raw.summary : path === '/api/tracking-data' ? raw.trackingData : path === '/api/frames' ? frameList
        : path.startsWith('/api/frames/') ? raw.frames.find(frame => path.endsWith(frame.frame_id)) : path === '/api/reports' ? raw.reports
        : path === '/api/alerts' ? raw.alerts : path === '/api/assessments' ? raw.assessments : path === '/api/reviews' ? raw.reviews
        : path.startsWith('/api/tracks/') ? raw.tracks[path.split('/').pop()!] : undefined;
      return body === undefined ? new Response('not found', { status: 404 }) : Response.json(body);
    }));
    const result = await fetchRawAnalysis();
    expect(calls.every(url => url.startsWith('/api/'))).toBe(true);
    expect(calls.filter(url => url.startsWith('/api/frames/'))).toHaveLength(raw.frames.length);
    expect(calls.filter(url => url.startsWith('/api/tracks/')).map(url => url.split('/').pop()).sort()).toEqual(['T0013', 'T0054']);
    expect(result.offframeTracks.map(track => track.track_id).sort()).toEqual(['T0013', 'T0054']);
  });
});
