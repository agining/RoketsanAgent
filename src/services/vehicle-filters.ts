import type { TrackingData, VehicleTrack } from '../types/tracking';
import { getPositionAtTime } from './playback';
import { calculateDistanceToBase, deriveMovementState } from './vehicle-metrics';
export type MovementFilter = 'moving' | 'stationary' | 'approaching' | 'leaving';
export interface VehicleFilters { searchQuery: string; selectedZone: string | null; activeMovementStates: MovementFilter[]; minSpeed: number | null; maxSpeed: number | null }
export const defaultFilters: VehicleFilters = { searchQuery: '', selectedZone: null, activeMovementStates: [], minSpeed: null, maxSpeed: null };
// zones.json supplies centers only. This is proximity, not an inferred zone boundary.
export const ZONE_PROXIMITY_KM = 0.75;
export function vehicleSnapshot(track: VehicleTrack, data: TrackingData, time: number) {
  const position = getPositionAtTime(track, time);
  const state = deriveMovementState(track, time, data.base);
  return { track, position, ...state, distanceKm: position ? calculateDistanceToBase(position, data.base) : null };
}
export function filterVehicles(data: TrackingData, filters: VehicleFilters, time: number) {
  const zone = data.zones.find(zone => zone.name === filters.selectedZone);
  const query = filters.searchQuery.trim().toLowerCase();
  return data.tracks.filter(track => track.id.toLowerCase().includes(query)).map(track => vehicleSnapshot(track, data, time)).filter(vehicle => {
    const { position, motion, baseTrend } = vehicle;
    if (filters.activeMovementStates.length && !filters.activeMovementStates.some(state => ({ moving: motion === 'MOVING', stationary: motion === 'STATIONARY', approaching: baseTrend === 'APPROACHING BASE', leaving: baseTrend === 'LEAVING BASE' })[state])) return false;
    if (filters.minSpeed !== null && (!position || position.speedKmh < filters.minSpeed)) return false;
    if (filters.maxSpeed !== null && (!position || position.speedKmh > filters.maxSpeed)) return false;
    if (filters.selectedZone && (!zone || !position || calculateDistanceToBase(position, { lat: zone.center[0], lon: zone.center[1] }) > ZONE_PROXIMITY_KM)) return false;
    return true;
  });
}
