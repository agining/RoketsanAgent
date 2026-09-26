import { describe, expect, it } from 'vitest';
import snapshot from '../../tests/fixtures/api-snapshot.json';
import { buildAnalysis, type RawAnalysis } from './analysisService';
import { analysisPlaybackBounds, clockSeconds, distanceAtTime, positionAtTime, selectedTrackEventFeatures, timelineEvents, untrackedVisibleAt } from './analysis-playback';

const analysis = buildAnalysis(structuredClone(snapshot) as unknown as RawAnalysis);
const entity = analysis.entities.find(item => item.track_id === 'T0106')!;

describe('analysis playback', () => {
  it('interpolates between API track points and hides tracks before they start', () => {
    const [a, b] = entity.points;
    expect(positionAtTime(entity, clockSeconds(a.time) - 1)).toBeNull();
    const mid = positionAtTime(entity, (clockSeconds(a.time) + clockSeconds(b.time)) / 2)!;
    expect(mid.interpolated).toBe(true);
    expect(mid.lat).toBeCloseTo((a.lat + b.lat) / 2, 9);
    const after = positionAtTime(entity, clockSeconds(entity.last_seen) + 60)!;
    expect(after.stale).toBe(true);
  });

  it('interpolates the API distance to base', () => {
    const points = [{ time: '12:00', dist_to_base_m: 1000 }, { time: '12:10', dist_to_base_m: 400 }];
    expect(distanceAtTime(points, clockSeconds('11:59'))).toBeNull();
    expect(distanceAtTime(points, clockSeconds('12:05'))).toBe(700);
    expect(distanceAtTime(points, clockSeconds('12:30'))).toBe(400);
  });

  it('covers track points and frame capture times', () => {
    const bounds = analysisPlaybackBounds(analysis);
    const times = analysis.entities.flatMap(item => item.points.map(point => clockSeconds(point.time)));
    expect(bounds.minTime).toBe(Math.min(...times, ...analysis.frames.map(frame => clockSeconds(frame.capture_time))));
    expect(bounds.maxTime).toBeGreaterThan(bounds.minTime);
  });

  it('builds timeline events from API alerts, stops and reports', () => {
    const events = timelineEvents(analysis);
    expect(events.filter(event => event.type === 'RISK')).toHaveLength(analysis.alerts.length);
    expect(events.filter(event => event.type === 'REPORT')).toHaveLength(analysis.reports.length);
    expect(events.map(event => event.timestamp)).toEqual([...events.map(event => event.timestamp)].sort((x, y) => x - y));
  });

  it('marks the observation, API stops and reports of the selected track', () => {
    const features = selectedTrackEventFeatures(entity, clockSeconds('23:59')).features.map(feature => feature.properties.type);
    expect(features).toContain('OBSERVATION');
    expect(features.filter(type => type === 'STOP')).toHaveLength(entity.features?.stops.length ?? 0);
  });

  it('shows untracked detections from their capture time', () => {
    const item = analysis.untracked[0];
    const capture = clockSeconds(item.capture_time);
    expect(untrackedVisibleAt(item, capture - 1)).toBeNull();
    expect(untrackedVisibleAt(item, capture)).toEqual({ stale: false, active: true });
    expect(untrackedVisibleAt(item, capture + 600)?.stale).toBe(true);
  });
});
