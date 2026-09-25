import type { TrackPoint, VehicleTrack } from '../types/tracking';

export interface TimedPoint extends TrackPoint { timestamp: number }
export interface VehiclePosition {
  lat: number; lon: number; heading: number | null; speedKmh: number;
  previous: TimedPoint; next: TimedPoint; segmentIndex: number;
}
const prepared = new WeakMap<VehicleTrack, TimedPoint[]>();
/** Seconds from the dataset's first day. Source ordering resolves midnight rollovers. */
export function timedPoints(track: VehicleTrack): TimedPoint[] {
  const cached = prepared.get(track); if (cached) return cached;
  let day = 0, last = -1;
  const points = track.points.map(point => {
    const [hours, minutes] = point.time.split(':').map(Number);
    let timestamp = hours * 3600 + minutes * 60 + day;
    if (timestamp < last) { day += 86400; timestamp += 86400; }
    last = timestamp;
    return { ...point, timestamp };
  });
  prepared.set(track, points); return points;
}
export function playbackBounds(tracks: VehicleTrack[]) {
  let minTime = Infinity, maxTime = -Infinity;
  for (const track of tracks) {
    const points = timedPoints(track);
    if (!points.length) continue;
    minTime = Math.min(minTime, points[0].timestamp);
    maxTime = Math.max(maxTime, points[points.length - 1].timestamp);
  }
  return Number.isFinite(minTime) ? { minTime, maxTime } : { minTime: 0, maxTime: 0 };
}
const radians = (degrees: number) => degrees * Math.PI / 180;
const longitudeDelta = (a: number, b: number) => ((b - a + 540) % 360) - 180;
export function calculateHeading(a: TrackPoint, b: TrackPoint): number | null {
  if (a.lat === b.lat && a.lon === b.lon) return null;
  const delta = radians(longitudeDelta(a.lon, b.lon)), lat1 = radians(a.lat), lat2 = radians(b.lat);
  return (Math.atan2(Math.sin(delta) * Math.cos(lat2), Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(delta)) * 180 / Math.PI + 360) % 360;
}
export function calculateApproxSpeed(a: TimedPoint, b: TimedPoint): number {
  const seconds = b.timestamp - a.timestamp; if (seconds <= 0) return 0;
  const h = Math.sin(radians(b.lat - a.lat) / 2) ** 2 + Math.cos(radians(a.lat)) * Math.cos(radians(b.lat)) * Math.sin(radians(longitudeDelta(a.lon, b.lon)) / 2) ** 2;
  return 6371 * 2 * Math.asin(Math.sqrt(Math.min(1, h))) / seconds * 3600;
}
export function interpolateTrackPosition(a: TimedPoint, b: TimedPoint, time: number) {
  const fraction = b.timestamp === a.timestamp ? 1 : Math.max(0, Math.min(1, (time - a.timestamp) / (b.timestamp - a.timestamp)));
  return { lat: a.lat + (b.lat - a.lat) * fraction, lon: ((a.lon + longitudeDelta(a.lon, b.lon) * fraction + 540) % 360) - 180 };
}
export function getPositionAtTime(track: VehicleTrack, time: number): VehiclePosition | null {
  const points = timedPoints(track);
  if (!points.length || time < points[0].timestamp || time > points[points.length - 1].timestamp) return null;
  // Upper-bound search also resolves duplicate timestamps without division by zero.
  let low = 0, high = points.length;
  while (low < high) { const mid = (low + high) >>> 1; if (points[mid].timestamp <= time) low = mid + 1; else high = mid; }
  const index = Math.min(Math.max(0, low - 1), Math.max(0, points.length - 2));
  const previous = points[index], next = points[Math.min(index + 1, points.length - 1)];
  return { ...interpolateTrackPosition(previous, next, time), previous, next, segmentIndex: index, heading: calculateHeading(previous, next), speedKmh: calculateApproxSpeed(previous, next) };
}
export function formatTime(time: number): string {
  const whole = Math.floor(time), day = Math.floor(whole / 86400);
  const clock = [Math.floor(whole / 3600) % 24, Math.floor(whole / 60) % 60, whole % 60].map(value => String(value).padStart(2, '0')).join(':');
  return day ? `Day ${day + 1} · ${clock}` : clock;
}
