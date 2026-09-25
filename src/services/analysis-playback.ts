import type {
  AnalysisData,
  AnalysisEntity,
  AnalysisReport,
  BehaviorHistoryEntry,
  MovementHistoryEntry,
  PositionHistoryEntry,
  UntrackedObservation,
} from '../types/analysis';
import { formatBehavior, formatMovementState } from './formatters';

export type TimelineEventType = 'APPROACHING_BASE' | 'LEAVING_BASE' | 'STATIONARY' | 'LOITERING' | 'CIRCLING' | 'REPORT';

export interface TimelineEvent {
  id: string;
  trackId: string;
  time: string;
  timestamp: number;
  type: TimelineEventType;
  label: string;
}

export interface PlaybackPosition {
  time: string;
  timestamp: number;
  lat: number;
  lon: number;
  zone: string;
  distance_to_base_m: number;
  stale: boolean;
  interpolated: boolean;
  previous: PositionHistoryEntry;
  next: PositionHistoryEntry;
}

export interface TrailFeatureProperties {
  trackId: string;
  selected: boolean;
  color: string;
  opacity: number;
  width: number;
}

export interface TrailArrowProperties {
  trackId: string;
  selected: boolean;
  heading: number;
  color: string;
  opacity: number;
}

export type LineStringFeature = {
  type: 'Feature';
  properties: TrailFeatureProperties;
  geometry: { type: 'LineString'; coordinates: [number, number][] };
};

export type PointFeature<TProperties extends object> = {
  type: 'Feature';
  properties: TProperties;
  geometry: { type: 'Point'; coordinates: [number, number] };
};

export type FeatureCollection<TFeature> = {
  type: 'FeatureCollection';
  features: TFeature[];
};

export function clockSeconds(time: string): number {
  const [hours = 0, minutes = 0, seconds = 0] = time.split(':').map(Number);
  return hours * 3600 + minutes * 60 + seconds;
}

export function formatClock(time: number): string {
  const bounded = Math.max(0, Math.floor(time));
  const hours = Math.floor(bounded / 3600) % 24;
  const minutes = Math.floor(bounded / 60) % 60;
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`;
}

const pointTime = (point: PositionHistoryEntry) => clockSeconds(point.time);

export function analysisPlaybackBounds(analysis: AnalysisData) {
  const times = analysis.entities.flatMap(entity => entity.position_history.map(pointTime));
  if (!times.length) return { minTime: 0, maxTime: 0 };
  return { minTime: Math.min(...times), maxTime: Math.max(...times) };
}

function sortedPositions(entity: AnalysisEntity) {
  return [...entity.position_history].sort((a, b) => pointTime(a) - pointTime(b));
}

export function positionAtTime(entity: AnalysisEntity, time: number): PlaybackPosition | null {
  const points = sortedPositions(entity);
  if (!points.length) return null;
  const firstTime = pointTime(points[0]);
  const last = points[points.length - 1];
  const lastTime = pointTime(last);
  if (time < firstTime) return null;
  if (time >= lastTime) {
    return { ...last, timestamp: lastTime, stale: time > lastTime, interpolated: false, previous: last, next: last };
  }
  let low = 0, high = points.length;
  while (low < high) {
    const mid = (low + high) >>> 1;
    if (pointTime(points[mid]) <= time) low = mid + 1;
    else high = mid;
  }
  const index = Math.max(0, low - 1);
  const previous = points[index];
  const next = points[Math.min(index + 1, points.length - 1)];
  const previousTime = pointTime(previous);
  const nextTime = pointTime(next);
  if (previousTime === nextTime || time === previousTime) {
    return { ...previous, timestamp: previousTime, stale: false, interpolated: false, previous, next };
  }
  const fraction = Math.max(0, Math.min(1, (time - previousTime) / (nextTime - previousTime)));
  return {
    time: formatClock(time),
    timestamp: time,
    lat: previous.lat + (next.lat - previous.lat) * fraction,
    lon: previous.lon + (next.lon - previous.lon) * fraction,
    zone: previous.zone,
    distance_to_base_m: previous.distance_to_base_m + (next.distance_to_base_m - previous.distance_to_base_m) * fraction,
    stale: false,
    interpolated: true,
    previous,
    next,
  };
}

const degrees = (radians: number) => radians * 180 / Math.PI;
const radians = (degreesValue: number) => degreesValue * Math.PI / 180;
function bearing(a: { lat: number; lon: number }, b: { lat: number; lon: number }): number {
  if (a.lat === b.lat && a.lon === b.lon) return 0;
  const lat1 = radians(a.lat), lat2 = radians(b.lat);
  const deltaLon = radians(b.lon - a.lon);
  const y = Math.sin(deltaLon) * Math.cos(lat2);
  const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(deltaLon);
  return (degrees(Math.atan2(y, x)) + 360) % 360;
}

export function headingAtTime(entity: AnalysisEntity, time: number): number | null {
  const position = positionAtTime(entity, time);
  if (!position) return null;
  if (position.previous !== position.next) return bearing(position.previous, position.next);
  const points = sortedPositions(entity);
  const index = points.findIndex(point => point.time === position.time);
  const previous = points[Math.max(0, index - 1)];
  const next = points[Math.min(points.length - 1, index + 1)];
  if (!previous || !next || previous === next) return null;
  return bearing(previous, next);
}

function latestAt<T extends { time: string }>(items: T[], time: number): T | null {
  let latest: T | null = null;
  for (const item of items) {
    if (clockSeconds(item.time) <= time && (!latest || clockSeconds(item.time) >= clockSeconds(latest.time))) latest = item;
  }
  return latest;
}

export function movementAtTime(entity: AnalysisEntity, time: number): MovementHistoryEntry | null {
  return latestAt(entity.movement_history, time);
}

export function behaviorAtTime(entity: AnalysisEntity, time: number): BehaviorHistoryEntry | null {
  return latestAt(entity.behavior_history, time);
}

export function reportsUntil(entity: AnalysisEntity, time: number): AnalysisReport[] {
  return entity.reports.filter(report => clockSeconds(report.time) <= time).sort((a, b) => clockSeconds(a.time) - clockSeconds(b.time));
}

export function reportsAtTime(entity: AnalysisEntity, time: number, windowSeconds = 150): AnalysisReport[] {
  return entity.reports.filter(report => Math.abs(clockSeconds(report.time) - time) <= windowSeconds);
}

export function untrackedVisibleAt(item: UntrackedObservation, time: number) {
  const capture = clockSeconds(item.capture_time);
  return time >= capture ? { stale: time > capture + 300, active: Math.abs(time - capture) <= 150 } : null;
}

export function trackTrail(entity: AnalysisEntity, time: number, mode: 'elapsed' | 'full' = 'elapsed'): [number, number][] {
  const points = sortedPositions(entity);
  if (mode === 'full') return points.map(point => [point.lon, point.lat]);
  const current = positionAtTime(entity, time);
  if (!current) return [];
  const coords = points.filter(point => pointTime(point) <= time).map(point => [point.lon, point.lat] as [number, number]);
  const last = coords[coords.length - 1];
  if (!last || last[0] !== current.lon || last[1] !== current.lat) coords.push([current.lon, current.lat]);
  return coords;
}

const trailPalette = ['#9ed0bd', '#d5b96f', '#82aac8', '#c98572', '#b895d6', '#7fc7c0', '#e0a36f', '#a7bd78'];
export function trackColor(trackId: string): string {
  const index = [...trackId].reduce((sum, char) => sum + char.charCodeAt(0), 0) % trailPalette.length;
  return trailPalette[index];
}

export function allTrackTrailFeatures(entities: AnalysisEntity[], time: number, mode: 'elapsed' | 'full' | 'off', selectedTrackId: string | null, visibleTrackIds?: ReadonlySet<string>): FeatureCollection<LineStringFeature> {
  if (mode === 'off') return { type: 'FeatureCollection', features: [] };
  return {
    type: 'FeatureCollection',
    features: entities.flatMap(entity => {
      if (visibleTrackIds && !visibleTrackIds.has(entity.track_id)) return [];
      const coordinates = trackTrail(entity, time, mode);
      if (coordinates.length < 2) return [];
      const selected = entity.track_id === selectedTrackId;
      return [{
        type: 'Feature' as const,
        properties: { trackId: entity.track_id, selected, color: trackColor(entity.track_id), opacity: selected ? 0.98 : selectedTrackId ? 0.22 : 0.42, width: selected ? 4.8 : 2.1 },
        geometry: { type: 'LineString' as const, coordinates },
      }];
    }),
  };
}

export function trailArrowFeatures(entities: AnalysisEntity[], time: number, mode: 'elapsed' | 'full' | 'off', selectedTrackId: string | null, visibleTrackIds?: ReadonlySet<string>): FeatureCollection<PointFeature<TrailArrowProperties>> {
  if (mode === 'off') return { type: 'FeatureCollection', features: [] };
  const features: PointFeature<TrailArrowProperties>[] = [];
  for (const entity of entities) {
    if (visibleTrackIds && !visibleTrackIds.has(entity.track_id)) continue;
    const coordinates = trackTrail(entity, time, mode);
    if (coordinates.length < 2) continue;
    const selected = entity.track_id === selectedTrackId;
    const every = selected ? 4 : 7;
    for (let index = every; index < coordinates.length; index += every) {
      const previous = coordinates[index - 1], current = coordinates[index];
      features.push({
        type: 'Feature',
        properties: { trackId: entity.track_id, selected, heading: bearing({ lat: previous[1], lon: previous[0] }, { lat: current[1], lon: current[0] }), color: trackColor(entity.track_id), opacity: selected ? 0.92 : selectedTrackId ? 0.18 : 0.32 },
        geometry: { type: 'Point', coordinates: current },
      });
    }
  }
  return { type: 'FeatureCollection', features };
}

export function selectedTrackEventFeatures(entity: AnalysisEntity | null, time: number): FeatureCollection<PointFeature<{ type: string; label: string }>> {
  if (!entity) return { type: 'FeatureCollection', features: [] };
  const features: PointFeature<{ type: string; label: string }>[] = [];
  const addAtTime = (eventTime: string, type: string, label: string) => {
    if (clockSeconds(eventTime) > time) return;
    const position = positionAtTime(entity, clockSeconds(eventTime));
    if (!position) return;
    features.push({ type: 'Feature', properties: { type, label }, geometry: { type: 'Point', coordinates: [position.lon, position.lat] } });
  };
  entity.movement_history.forEach(item => {
    if (item.state === 'STATIONARY') addAtTime(item.time, 'STOP', 'Hareketsiz');
  });
  entity.behavior_history.forEach(item => {
    if (item.behavior === 'LOITERING' || item.behavior === 'CIRCLING') addAtTime(item.time, item.behavior, formatBehavior(item.behavior));
  });
  entity.reports.forEach(report => addAtTime(report.time, 'REPORT', 'Saha raporu'));
  return { type: 'FeatureCollection', features };
}

export function timelineEvents(analysis: AnalysisData): TimelineEvent[] {
  const events: TimelineEvent[] = [];
  for (const entity of analysis.entities) {
    let lastMovement: string | null = null;
    entity.movement_history.forEach(entry => {
      const isEvent = ['APPROACHING_BASE', 'LEAVING_BASE', 'STATIONARY'].includes(entry.state) && entry.state !== lastMovement;
      if (isEvent) events.push({ id: `${entity.track_id}-${entry.time}-${entry.state}`, trackId: entity.track_id, time: entry.time, timestamp: clockSeconds(entry.time), type: entry.state as TimelineEventType, label: `${entity.track_id} · ${formatMovementState(entry.state)}` });
      lastMovement = entry.state;
    });
    let lastBehavior: string | null = null;
    entity.behavior_history.forEach(entry => {
      const isEvent = ['LOITERING', 'CIRCLING'].includes(entry.behavior) && entry.behavior !== lastBehavior;
      if (isEvent) events.push({ id: `${entity.track_id}-${entry.time}-${entry.behavior}`, trackId: entity.track_id, time: entry.time, timestamp: clockSeconds(entry.time), type: entry.behavior as TimelineEventType, label: `${entity.track_id} · ${formatBehavior(entry.behavior)}` });
      lastBehavior = entry.behavior;
    });
    entity.reports.forEach((report, index) => {
      events.push({ id: `${entity.track_id}-${report.time}-REPORT-${index}`, trackId: entity.track_id, time: report.time, timestamp: clockSeconds(report.time), type: 'REPORT', label: `${entity.track_id} · saha raporu` });
    });
  }
  return events.sort((a, b) => a.timestamp - b.timestamp || a.trackId.localeCompare(b.trackId));
}
