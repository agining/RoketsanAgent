import { getPositionAtTime, timedPoints } from "./playback";
import type { FeatureCollection, LineString } from 'geojson';
import type { TrackingData, VehicleTrack } from '../types/tracking';
/** Route geometry stays independent of marker positions for future playback. */
export function routeFeatures(tracks: VehicleTrack[]): FeatureCollection<LineString> {
  return { type: 'FeatureCollection', features: tracks.filter(track => track.points.length > 1).map(track => ({
    type: 'Feature', properties: { trackId: track.id }, geometry: { type: 'LineString', coordinates: track.points.map(point => [point.lon, point.lat]) },
  })) };
}
export function trackingBounds(data: Pick<TrackingData, 'base' | 'zones' | 'tracks'>): [[number, number], [number, number]] {
  const positions = [ [data.base.lon, data.base.lat], ...data.zones.map(zone => [zone.center[1], zone.center[0]]), ...data.tracks.flatMap(track => track.points.map(point => [point.lon, point.lat])) ];
  return positions.reduce<[[number, number], [number, number]]>((bounds, [lon, lat]) => [[Math.min(bounds[0][0], lon), Math.min(bounds[0][1], lat)], [Math.max(bounds[1][0], lon), Math.max(bounds[1][1], lat)]], [[Infinity, Infinity], [-Infinity, -Infinity]]);
}

/** Drawn above dim full routes; ends exactly at each vehicle's interpolated position. */
export function traveledFeatures(tracks: VehicleTrack[], time: number): FeatureCollection<LineString> {
  return { type: 'FeatureCollection', features: tracks.flatMap(track => {
    const points = timedPoints(track);
    if (points.length < 2 || time < points[0].timestamp) return [];
    const position = getPositionAtTime(track, time);
    const coordinates = position
      ? [...points.slice(0, position.segmentIndex + 1).map(point => [point.lon, point.lat]), [position.lon, position.lat]]
      : points.map(point => [point.lon, point.lat]);
    return [{ type: 'Feature' as const, properties: { trackId: track.id }, geometry: { type: 'LineString' as const, coordinates } }];
  }) };
}

export function futureFeatures(tracks: VehicleTrack[], time: number): FeatureCollection<LineString> {
  return { type: 'FeatureCollection', features: tracks.flatMap(track => {
    const points = timedPoints(track);
    if (points.length < 2 || time >= points[points.length - 1].timestamp) return [];
    const position = getPositionAtTime(track, time);
    const coordinates = position ? [[position.lon, position.lat], ...points.slice(position.segmentIndex + 1).map(point => [point.lon, point.lat])] : points.map(point => [point.lon, point.lat]);
    return [{ type: 'Feature' as const, properties: { trackId: track.id }, geometry: { type: 'LineString' as const, coordinates } }];
  }) };
}
