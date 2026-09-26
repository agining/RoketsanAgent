import type { AnalysisData, AnalysisEntity, AnalysisReport, AnalysisVehicle, RiskLevel, TrackPoint } from '../types/analysis';
import { formatRiskLevel, formatScenario } from './formatters';

/**
 * Playback helpers. They only place API data on the timeline/map (interpolating GPS points between
 * samples); risk, scenario and report verdicts are always the API's values.
 */

export type TimelineEventType = 'RISK' | 'STOP' | 'REPORT';

export interface TimelineEvent {
  id: string; trackId: string | null; time: string; timestamp: number; type: TimelineEventType; label: string; risk?: RiskLevel;
}

export interface PlaybackPosition {
  time: string; timestamp: number; lat: number; lon: number;
  stale: boolean; interpolated: boolean; previous: TrackPoint; next: TrackPoint;
}

export interface TrailFeatureProperties { trackId: string; selected: boolean; color: string; opacity: number; width: number }
export interface TrailArrowProperties { trackId: string; selected: boolean; heading: number; color: string; opacity: number }

export type LineStringFeature = { type: 'Feature'; properties: TrailFeatureProperties; geometry: { type: 'LineString'; coordinates: [number, number][] } };
export type PointFeature<TProperties extends object> = { type: 'Feature'; properties: TProperties; geometry: { type: 'Point'; coordinates: [number, number] } };
export type FeatureCollection<TFeature> = { type: 'FeatureCollection'; features: TFeature[] };

export const RISK_WEIGHT: Record<RiskLevel, number> = { UNKNOWN: 0, LOW: 1, MEDIUM: 2, HIGH: 3, CRITICAL: 4 };

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

const pointTime = (point: { time: string }) => clockSeconds(point.time);

export function analysisPlaybackBounds(analysis: AnalysisData) {
  const times = [
    ...analysis.entities.flatMap(entity => entity.points.map(pointTime)),
    ...analysis.frames.map(frame => clockSeconds(frame.capture_time)),
  ];
  if (!times.length) return { minTime: 0, maxTime: 0 };
  return { minTime: Math.min(...times), maxTime: Math.max(...times) };
}

/** Linear interpolation between recorded GPS points; null before the track starts. */
export function positionAtTime(entity: Pick<AnalysisEntity, 'points'>, time: number): PlaybackPosition | null {
  const points = entity.points;
  if (!points.length) return null;
  const firstTime = pointTime(points[0]);
  const last = points[points.length - 1];
  const lastTime = pointTime(last);
  if (time < firstTime) return null;
  if (time >= lastTime) return { ...last, timestamp: lastTime, stale: time > lastTime, interpolated: false, previous: last, next: last };
  let low = 0, high = points.length;
  while (low < high) {
    const mid = (low + high) >>> 1;
    if (pointTime(points[mid]) <= time) low = mid + 1;
    else high = mid;
  }
  const index = Math.max(0, low - 1);
  const previous = points[index];
  const next = points[Math.min(index + 1, points.length - 1)];
  const previousTime = pointTime(previous), nextTime = pointTime(next);
  if (previousTime === nextTime || time === previousTime) return { ...previous, timestamp: previousTime, stale: false, interpolated: false, previous, next };
  const fraction = Math.max(0, Math.min(1, (time - previousTime) / (nextTime - previousTime)));
  return {
    time: formatClock(time), timestamp: time,
    lat: previous.lat + (next.lat - previous.lat) * fraction,
    lon: previous.lon + (next.lon - previous.lon) * fraction,
    stale: false, interpolated: true, previous, next,
  };
}

/** Interpolates the API's per-point distance to base (from /api/tracks/{id}). */
export function distanceAtTime(points: { time: string; dist_to_base_m: number }[], time: number): number | null {
  if (!points.length || time < pointTime(points[0])) return null;
  const after = points.findIndex(point => pointTime(point) >= time);
  if (after === -1) return points[points.length - 1].dist_to_base_m;
  if (after === 0 || pointTime(points[after]) === time) return points[after].dist_to_base_m;
  const a = points[after - 1], b = points[after];
  const fraction = (time - pointTime(a)) / (pointTime(b) - pointTime(a));
  return a.dist_to_base_m + (b.dist_to_base_m - a.dist_to_base_m) * fraction;
}

const degrees = (radians: number) => radians * 180 / Math.PI;
const radians = (degreesValue: number) => degreesValue * Math.PI / 180;
/** Screen bearing for the marker arrow only. */
function bearing(a: { lat: number; lon: number }, b: { lat: number; lon: number }): number {
  if (a.lat === b.lat && a.lon === b.lon) return 0;
  const lat1 = radians(a.lat), lat2 = radians(b.lat);
  const deltaLon = radians(b.lon - a.lon);
  const y = Math.sin(deltaLon) * Math.cos(lat2);
  const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(deltaLon);
  return (degrees(Math.atan2(y, x)) + 360) % 360;
}

export function headingAtTime(entity: Pick<AnalysisEntity, 'points'>, time: number): number | null {
  const position = positionAtTime(entity, time);
  if (!position) return null;
  if (position.previous !== position.next) return bearing(position.previous, position.next);
  const points = entity.points;
  const index = points.findIndex(point => point.time === position.time);
  const previous = points[Math.max(0, index - 1)];
  const next = points[Math.min(points.length - 1, index + 1)];
  if (!previous || !next || previous === next) return null;
  return bearing(previous, next);
}

export function reportsUntil(entity: AnalysisEntity, time: number): AnalysisReport[] {
  return entity.reports.filter(report => clockSeconds(report.time) <= time);
}

export function reportsAtTime(entity: AnalysisEntity, time: number, windowSeconds = 150): AnalysisReport[] {
  return entity.reports.filter(report => Math.abs(clockSeconds(report.time) - time) <= windowSeconds);
}

export function untrackedVisibleAt(item: AnalysisVehicle, time: number) {
  const capture = clockSeconds(item.capture_time);
  return time >= capture ? { stale: time > capture + 300, active: Math.abs(time - capture) <= 150 } : null;
}

export function trackTrail(entity: Pick<AnalysisEntity, 'points'>, time: number, mode: 'elapsed' | 'full' = 'elapsed'): [number, number][] {
  const points = entity.points;
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

/** Map markers for the selected track: API stop events, report times and the frame observation. */
export function selectedTrackEventFeatures(entity: AnalysisEntity | null, time: number): FeatureCollection<PointFeature<{ type: string; label: string }>> {
  if (!entity) return { type: 'FeatureCollection', features: [] };
  const features: PointFeature<{ type: string; label: string }>[] = [];
  const add = (type: string, label: string, lon: number, lat: number) => features.push({ type: 'Feature', properties: { type, label }, geometry: { type: 'Point', coordinates: [lon, lat] } });
  entity.features?.stops.forEach(stop => { if (clockSeconds(stop.start) <= time) add('STOP', `Duraklama ${stop.start}–${stop.end}`, stop.lon, stop.lat); });
  entity.reports.forEach(report => {
    if (clockSeconds(report.time) > time) return;
    const position = positionAtTime(entity, clockSeconds(report.time));
    if (position) add('REPORT', `${report.report_id} saha raporu`, position.lon, position.lat);
  });
  if (entity.vehicle && clockSeconds(entity.vehicle.capture_time) <= time) add('OBSERVATION', `${entity.vehicle.frame_id} karesi`, entity.vehicle.lon, entity.vehicle.lat);
  return { type: 'FeatureCollection', features };
}

/** Timeline markers: API alerts (final level ≥ ORTA), their stop events and field reports. */
export function timelineEvents(analysis: AnalysisData): TimelineEvent[] {
  const events: TimelineEvent[] = [];
  const entityByTrack = new Map(analysis.entities.map(entity => [entity.track_id, entity]));
  analysis.alerts.forEach((alert, index) => {
    const subject = alert.track_id ?? alert.vehicle_id ?? 'Araç';
    events.push({ id: `risk-${index}-${subject}`, trackId: alert.track_id, time: alert.time, timestamp: clockSeconds(alert.time), type: 'RISK', risk: alert.risk_level, label: `${subject} · ${formatRiskLevel(alert.risk_level)} · ${formatScenario(alert.scenario)}` });
    const entity = alert.track_id ? entityByTrack.get(alert.track_id) : null;
    entity?.features?.stops.forEach(stop => events.push({ id: `stop-${entity.track_id}-${stop.start}`, trackId: entity.track_id, time: stop.start, timestamp: clockSeconds(stop.start), type: 'STOP', label: `${entity.track_id} · ${stop.minutes} dk duraklama` }));
  });
  analysis.reports.forEach(report => events.push({ id: `report-${report.report_id}`, trackId: report.matched_track_id, time: report.time, timestamp: clockSeconds(report.time), type: 'REPORT', label: `${report.report_id} · saha raporu` }));
  return events.sort((a, b) => a.timestamp - b.timestamp || (a.trackId ?? '').localeCompare(b.trackId ?? ''));
}
