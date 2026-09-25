import { describe, expect, it } from 'vitest';
import { defaultFilters, filterVehicles } from './vehicle-filters';
import { futureFeatures, traveledFeatures } from './map-data';
import type { TrackingData } from '../types/tracking';
const data: TrackingData = { base: { name: 'Base', lat: 0, lon: 0 }, zones: [{ name: 'North', center: [0, .01] }], tracks: [
  { id: 'Approach', points: [{ time: '12:00', lat: 0, lon: .01 }, { time: '12:10', lat: 0, lon: 0 }] },
  { id: 'Parked', points: [{ time: '12:00', lat: 0, lon: .03 }, { time: '12:10', lat: 0, lon: .03 }] },
  { id: 'Depart', points: [{ time: '12:00', lat: 0, lon: 0 }, { time: '12:10', lat: 0, lon: .01 }] },
] };
const ids = (filters = defaultFilters, time = 43200) => filterVehicles(data, filters, time).map(vehicle => vehicle.track.id);
describe('vehicle filters', () => {
  it('matches trimmed case-insensitive search without mutating tracks', () => {
    expect(ids({ ...defaultFilters, searchQuery: ' APPro ' })).toEqual(['Approach']);
    expect(ids()).toHaveLength(3); expect(data.tracks[0].points).toHaveLength(2);
  });
  it('ORs movement states and ANDs other filter dimensions', () => {
    expect(ids({ ...defaultFilters, activeMovementStates: ['approaching'] })).toEqual(['Approach']);
    expect(ids({ ...defaultFilters, activeMovementStates: ['leaving'] })).toEqual(['Depart']);
    expect(ids({ ...defaultFilters, activeMovementStates: ['stationary', 'leaving'] })).toEqual(['Parked', 'Depart']);
    expect(ids({ ...defaultFilters, activeMovementStates: ['moving'], maxSpeed: 1 })).toEqual([]);
    expect(ids({ ...defaultFilters, minSpeed: 0, maxSpeed: 0 })).toEqual(['Parked']);
    expect(ids({ ...defaultFilters, minSpeed: 100, maxSpeed: 1 })).toEqual([]);
  });
  it('evaluates zone proximity and time-dependent membership', () => {
    const filters = { ...defaultFilters, selectedZone: 'North' };
    expect(ids(filters, 43200)).toEqual(['Approach']);
    expect(ids(filters, 43800)).toEqual(['Depart']);
    expect(ids({ ...defaultFilters, selectedZone: 'missing' })).toEqual([]);
    expect(ids({ ...defaultFilters, activeMovementStates: ['moving'] }, 44000)).toEqual([]);
    expect(ids(defaultFilters, 44000)).toHaveLength(3); // Completed routes stay searchable without live filters.
  });
  it('splits traveled and future geometry at the interpolated position', () => {
    const tracks = filterVehicles(data, { ...defaultFilters, searchQuery: 'Approach' }, 43500).map(vehicle => vehicle.track);
    const traveled = traveledFeatures(tracks, 43500), future = futureFeatures(tracks, 43500);
    expect(traveled.features).toHaveLength(1); expect(future.features).toHaveLength(1);
    expect(traveled.features[0].geometry.coordinates.at(-1)).toEqual(future.features[0].geometry.coordinates[0]);
    expect(future.features[0].geometry.coordinates.at(-1)).toEqual([0, 0]);
    expect(futureFeatures(tracks, 43800).features).toEqual([]);
    expect(futureFeatures(tracks, 43000).features[0].geometry.coordinates).toEqual([[.01, 0], [0, 0]]);
  });
});
