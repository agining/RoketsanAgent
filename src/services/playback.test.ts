import { describe, expect, it, beforeEach } from 'vitest';
import type { VehicleTrack } from '../types/tracking';
import { calculateApproxSpeed, calculateHeading, formatTime, getPositionAtTime, playbackBounds, timedPoints } from './playback';
import { traveledFeatures } from './map-data';
import { usePlaybackStore } from '../store/playback';
const track: VehicleTrack = { id: 'arbitrary-id', points: [{ time: '12:00', lat: 0, lon: 0 }, { time: '12:05', lat: 0, lon: 1 }, { time: '12:10', lat: 1, lon: 1 }] };
describe('time interpolation', () => {
  it('interpolates the midpoint and calculates direction and segment speed', () => {
    const position = getPositionAtTime(track, 12 * 3600 + 150)!;
    expect(position.lat).toBe(0); expect(position.lon).toBeCloseTo(.5);
    expect(position.heading).toBeCloseTo(90); expect(position.speedKmh).toBeCloseTo(1334.34, 1);
    expect(position.previous.time).toBe('12:00'); expect(position.next.time).toBe('12:05');
  });
  it('includes endpoint positions but never extrapolates', () => {
    expect(getPositionAtTime(track, 43199)).toBeNull(); expect(getPositionAtTime(track, 43801)).toBeNull();
    expect(getPositionAtTime(track, 43200)?.lon).toBe(0); expect(getPositionAtTime(track, 43800)?.lat).toBe(1);
    expect(getPositionAtTime(track, 43500)?.heading).toBeCloseTo(0);
  });
  it('handles empty, stationary, single point and irregular tracks', () => {
    expect(getPositionAtTime({ id: 'empty', points: [] }, 0)).toBeNull();
    const single = { id: 'single', points: [track.points[0]] };
    expect(getPositionAtTime(single, 43200)?.speedKmh).toBe(0);
    expect(getPositionAtTime(single, 43201)).toBeNull();
    expect(calculateHeading(track.points[0], track.points[0])).toBeNull();
    const irregular = { id: 'irregular', points: [track.points[0], { time: '12:20', lat: 0, lon: 1 }] };
    expect(getPositionAtTime(irregular, 43500)?.lon).toBeCloseTo(.25);
  });
  it('unwraps midnight and includes different vehicle ranges', () => {
    const night = { id: 'night', points: [{ time: '23:55', lat: 0, lon: 0 }, { time: '00:05', lat: 0, lon: 1 }] };
    expect(getPositionAtTime(night, 86400)?.lon).toBeCloseTo(.5);
    expect(playbackBounds([track, night])).toEqual({ minTime: 43200, maxTime: 86700 });
    expect(formatTime(86400)).toBe('Day 2 · 00:00:00');
  });
  it('takes the short longitude path across the dateline', () => {
    const crossing = { id: 'crossing', points: [{ time: '12:00', lat: 0, lon: 179 }, { time: '12:05', lat: 0, lon: -179 }] };
    expect(Math.abs(getPositionAtTime(crossing, 43350)!.lon)).toBe(180);
  });
  it('handles repeated timestamps and zero-duration speed', () => {
    const duplicate = { id: 'duplicate', points: [track.points[0], { ...track.points[0], lon: .1 }, track.points[1]] };
    expect(getPositionAtTime(duplicate, 43200)?.lon).toBeCloseTo(.1);
    const points = timedPoints(duplicate); expect(calculateApproxSpeed(points[0], points[1])).toBe(0);
    expect(getPositionAtTime({ id: 'same-time', points: duplicate.points.slice(0, 2) }, 43200)?.lon).toBeCloseTo(.1);
  });
  it('cuts traveled geometry at the vehicle and keeps completed routes', () => {
    expect(traveledFeatures([track], 43199).features).toHaveLength(0);
    expect(traveledFeatures([track], 43350).features[0].geometry.coordinates).toEqual([[0, 0], [.5, 0]]);
    expect(traveledFeatures([track], 44000).features[0].geometry.coordinates).toEqual([[0, 0], [1, 0], [1, 1]]);
  });
});
describe('playback state', () => {
  beforeEach(() => { usePlaybackStore.getState().initialize(100, 200); usePlaybackStore.getState().setSpeed(1); });
  it('uses elapsed seconds, command-center speeds and simulation scale independently of frame count', () => {
    const store = usePlaybackStore.getState(); store.togglePlaying(); store.setSpeed(2); store.advance(.5);
    expect(usePlaybackStore.getState().currentTime).toBe(160);
    store.setSpeed(4); store.advance(.5); expect(usePlaybackStore.getState().currentTime).toBe(200);
    store.advance(2); expect(usePlaybackStore.getState().currentTime).toBe(200);
  });
  it('clamps seeking, pauses at end, replays and resets', () => {
    const store = usePlaybackStore.getState(); store.seek(1); expect(usePlaybackStore.getState().currentTime).toBe(100);
    store.togglePlaying(); store.advance(1000); expect(usePlaybackStore.getState().currentTime).toBe(200); expect(usePlaybackStore.getState().isPlaying).toBe(false);
    store.togglePlaying(); expect(usePlaybackStore.getState().currentTime).toBe(100); expect(usePlaybackStore.getState().isPlaying).toBe(true);
    store.restart(); expect(usePlaybackStore.getState().isPlaying).toBe(false);
    store.seek(300); expect(usePlaybackStore.getState().currentTime).toBe(200);
  });
});
