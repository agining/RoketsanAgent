import type { BaseLocation, VehicleTrack } from '../types/tracking';
import { calculateApproxSpeed, getPositionAtTime, interpolateTrackPosition, timedPoints } from './playback';
type Coordinates = { lat: number; lon: number };
export interface MetricSample { time: number; value: number }
/** Great-circle distance in kilometers. */
export function calculateDistanceToBase(point: Coordinates, base: Coordinates): number {
  const rad = Math.PI / 180;
  const h = Math.sin((base.lat - point.lat) * rad / 2) ** 2 + Math.cos(point.lat * rad) * Math.cos(base.lat * rad) * Math.sin((base.lon - point.lon) * rad / 2) ** 2;
  return 12742 * Math.asin(Math.sqrt(Math.min(1, Math.max(0, h))));
}
const distances = new WeakMap<VehicleTrack, number[]>();
function cumulativeDistances(track: VehicleTrack) {
  const existing = distances.get(track); if (existing) return existing;
  const points = timedPoints(track); let total = 0;
  const result = points.map((point, index) => { if (index) total += calculateDistanceToBase(points[index - 1], point); return total; });
  distances.set(track, result); return result;
}
/** Distance traveled up to the requested time, including the current partial segment. */
export function calculateTotalDistance(track: VehicleTrack, time = Infinity): number {
  const points = timedPoints(track), cumulative = cumulativeDistances(track);
  if (!points.length || time < points[0].timestamp) return 0;
  if (time >= points[points.length - 1].timestamp) return cumulative[cumulative.length - 1];
  const position = getPositionAtTime(track, time)!;
  return cumulative[position.segmentIndex] + calculateDistanceToBase(position.previous, position);
}
export function calculateTrackSpeedSeries(track: VehicleTrack): MetricSample[] {
  const points = timedPoints(track);
  return points.map((point, index) => ({ time: point.timestamp, value: calculateApproxSpeed(points[Math.min(index, Math.max(0, points.length - 2))], points[Math.min(index + 1, points.length - 1)]) }));
}
export function calculateDistanceSeries(track: VehicleTrack, base: BaseLocation): MetricSample[] {
  return timedPoints(track).map(point => ({ time: point.timestamp, value: calculateDistanceToBase(point, base) }));
}
export const STATIONARY_SPEED_KMH = 0.5;
/** Local distance trend, not simply the difference between segment endpoints. */
export function deriveMovementState(track: VehicleTrack, time: number, base: BaseLocation) {
  const position = getPositionAtTime(track, time);
  if (!position) return { motion: 'OUTSIDE TRACK', baseTrend: null } as const;
  if (position.speedKmh < STATIONARY_SPEED_KMH) return { motion: 'STATIONARY', baseTrend: null } as const;
  const start = Math.max(position.previous.timestamp, time - 1), end = Math.min(position.next.timestamp, time + 1);
  const before = interpolateTrackPosition(position.previous, position.next, start), after = interpolateTrackPosition(position.previous, position.next, end);
  const rate = end > start ? (calculateDistanceToBase(after, base) - calculateDistanceToBase(before, base)) / (end - start) * 3600 : 0;
  return { motion: 'MOVING', baseTrend: rate < -0.05 ? 'APPROACHING BASE' : rate > 0.05 ? 'LEAVING BASE' : 'STEADY BASE DISTANCE' } as const;
}
const historyCache = new WeakMap<VehicleTrack, WeakMap<BaseLocation, ReturnType<typeof buildHistory>>>();
function buildHistory(track: VehicleTrack, base: BaseLocation) {
  const speeds = calculateTrackSpeedSeries(track);
  return timedPoints(track).map((point, index) => ({ ...point, speedKmh: speeds[index].value, distanceKm: calculateDistanceToBase(point, base) }));
}
export function recentTrackPoints(track: VehicleTrack, base: BaseLocation, time: number, limit = 5) {
  let bases = historyCache.get(track); if (!bases) { bases = new WeakMap(); historyCache.set(track, bases); }
  let history = bases.get(base); if (!history) { history = buildHistory(track, base); bases.set(base, history); }
  let low = 0, high = history.length;
  while (low < high) { const mid = (low + high) >>> 1; if (history[mid].timestamp <= time) low = mid + 1; else high = mid; }
  return history.slice(Math.max(0, low - limit), low).reverse();
}
export function selectedVehicleMetrics(track: VehicleTrack, time: number, base: BaseLocation) {
  const points = timedPoints(track), position = getPositionAtTime(track, time);
  const elapsedSeconds = points.length ? Math.max(0, Math.min(time, points[points.length - 1].timestamp) - points[0].timestamp) : 0;
  const directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
  return { position, distanceToBase: position ? calculateDistanceToBase(position, base) : null, totalDistance: calculateTotalDistance(track, time), elapsedSeconds,
    direction: position?.heading != null ? directions[Math.round(position.heading / 45) % 8] : null,
    ...deriveMovementState(track, time, base), history: recentTrackPoints(track, base, time) };
}
export function formatDuration(seconds: number) {
  const whole = Math.floor(seconds);
  return `${Math.floor(whole / 3600)}h ${String(Math.floor(whole / 60) % 60).padStart(2, '0')}m ${String(whole % 60).padStart(2, '0')}s`;
}
