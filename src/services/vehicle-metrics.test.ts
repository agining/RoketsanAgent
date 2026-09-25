import { describe, expect, it } from 'vitest';
import { calculateDistanceToBase, calculateTotalDistance, calculateTrackSpeedSeries, calculateDistanceSeries, deriveMovementState, selectedVehicleMetrics, recentTrackPoints } from './vehicle-metrics';
import { useTrackingStore } from '../store/tracking';
import type { VehicleTrack } from '../types/tracking';
const base = { name: 'Base', lat: 0, lon: 0 };
const track: VehicleTrack = { id: 'test', points: [{ time: '12:00', lat: 0, lon: -.01 }, { time: '12:10', lat: 0, lon: .01 }, { time: '12:20', lat: 0, lon: .01 }] };
describe('selected vehicle metrics', () => {
  it('calculates great-circle kilometers and cumulative partial distance', () => {
    expect(calculateDistanceToBase(base, base)).toBe(0);
    expect(calculateDistanceToBase({ lat: 0, lon: 1 }, base)).toBeCloseTo(111.195, 2);
    expect(calculateTotalDistance(track, 43199)).toBe(0);
    expect(calculateTotalDistance(track, 43500)).toBeCloseTo(1.11195, 4);
    expect(calculateTotalDistance(track)).toBeCloseTo(2.2239, 4);
    expect(calculateTotalDistance(track, 45000)).toBeCloseTo(2.2239, 4);
  });
  it('distinguishes approach and departure inside the same segment', () => {
    expect(deriveMovementState(track, 43300, base)).toEqual({ motion: 'MOVING', baseTrend: 'APPROACHING BASE' });
    expect(deriveMovementState(track, 43700, base)).toEqual({ motion: 'MOVING', baseTrend: 'LEAVING BASE' });
    expect(deriveMovementState(track, 43500, base).baseTrend).toBe('STEADY BASE DISTANCE');
    expect(deriveMovementState(track, 44000, base)).toEqual({ motion: 'STATIONARY', baseTrend: null });
    expect(deriveMovementState(track, 45000, base).motion).toBe('OUTSIDE TRACK');
  });
  it('provides series, recent history without future samples, and elapsed duration', () => {
    expect(calculateTrackSpeedSeries(track).map(sample => sample.value)).toEqual([expect.closeTo(13.3434, 3), 0, 0]);
    expect(calculateDistanceSeries(track, base)).toHaveLength(3);
    expect(recentTrackPoints(track, base, 43199)).toEqual([]);
    expect(recentTrackPoints(track, base, 43800).map(point => point.time)).toEqual(['12:10', '12:00']);
    expect(selectedVehicleMetrics(track, 43300, base).elapsedSeconds).toBe(100);
    expect(selectedVehicleMetrics(track, 45000, base).elapsedSeconds).toBe(1200);
    expect(selectedVehicleMetrics(track, 43199, base).elapsedSeconds).toBe(0);
    expect(selectedVehicleMetrics(track, 45000, base).distanceToBase).toBeNull();
  });
  it('supports empty and single-point tracks', () => {
    const empty = { id: 'empty', points: [] };
    expect(calculateTotalDistance(empty)).toBe(0);
    expect(calculateTrackSpeedSeries(empty)).toEqual([]);
    const single = { id: 'single', points: [track.points[0]] };
    expect(calculateTrackSpeedSeries(single)[0].value).toBe(0);
    expect(deriveMovementState(single, 43200, base).motion).toBe('STATIONARY');
  });
  it('clears follow on deselect or camera actions while retaining selection', () => {
    const store = useTrackingStore.getState();
    store.selectTrack('test'); store.setFollowVehicle(true); expect(useTrackingStore.getState().followVehicle).toBe(true);
    store.requestView('route'); expect(useTrackingStore.getState().followVehicle).toBe(false);
    expect(useTrackingStore.getState().selectedTrackId).toBe('test');
    store.setFollowVehicle(true); store.selectTrack(null); expect(useTrackingStore.getState().followVehicle).toBe(false);
    store.setFollowVehicle(true); expect(useTrackingStore.getState().followVehicle).toBe(false);
  });
});
