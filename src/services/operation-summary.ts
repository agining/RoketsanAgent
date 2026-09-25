import type { AnalysisData, AnalysisFrame, AnalysisVehicle, RiskLevel } from '../types/analysis';
import type { TrackingData } from '../types/tracking';
import { analysisForTrack, buildAnalysisIndex, clockMinutes, RISK_WEIGHT, vehicleType } from './analysis';
export interface CriticalVehicleRow { trackId: string; type: string; zone: string; distanceM: number; scenario: string; reason: string; risk: RiskLevel }
export interface ZoneSummaryRow { zone: string; vehicles: number; elevated: number; untracked: number; conflicts: number; riskScore: number }
export { clockMinutes };
/** Builds a time-scoped UI snapshot from entity history; analysis.json itself has no frame collection. */
export function currentFrameAtTime(analysis: AnalysisData, playbackSeconds: number, toleranceMinutes = 2.5): AnalysisFrame | null {
  const minute = playbackSeconds / 60;
  const times = [...new Set([...analysis.entities.flatMap(entity => entity.movement_history.map(entry => entry.time)), ...analysis.untracked_observations.map(item => item.capture_time)])];
  const capture = times.map(time => ({ time, distance: Math.abs(clockMinutes(time) - minute) })).filter(item => item.distance <= toleranceMinutes).sort((a, b) => a.distance - b.distance)[0]?.time;
  if (!capture) return null;
  const index = buildAnalysisIndex(analysis);
  const vehicles = analysis.entities.filter(entity => entity.movement_history.some(entry => entry.time === capture)).flatMap(entity => index.byTrackId.get(entity.track_id) ?? []);
  vehicles.push(...index.untracked.filter(item => item.capture_time === capture));
  const counts = { LOW: 0, MEDIUM: 0, HIGH: 0, CRITICAL: 0, UNKNOWN: 0 } satisfies Record<RiskLevel, number>;
  vehicles.forEach(vehicle => counts[vehicle.risk_level]++);
  const top = [...vehicles].sort((a, b) => RISK_WEIGHT[b.risk_level] - RISK_WEIGHT[a.risk_level])[0];
  return { frame_id: `snapshot-${capture.replace(':', '')}`, capture_time: capture, zone: top?.zone ?? 'Operasyon alanı', risk_level: top?.risk_level ?? 'UNKNOWN', counts, top_vehicle_id: top?.vehicle_id ?? null, vehicles, reports: [] };
}
export function criticalVehiclesAtTime(data: TrackingData, playbackSeconds: number, limit = 6): CriticalVehicleRow[] {
  const index = buildAnalysisIndex(data.analysis);
  return data.tracks.flatMap(track => {
    const vehicle = analysisForTrack(index, track.id, playbackSeconds);
    if (!vehicle || !['HIGH', 'CRITICAL'].includes(vehicle.risk_level)) return [];
    return [{ trackId: track.id, type: vehicleType(vehicle), zone: vehicle.zone, distanceM: vehicle.dist_to_base_m, scenario: vehicle.scenario, reason: vehicle.risk_reasons[0] ?? 'Risk gerekçesi sağlanmamış.', risk: vehicle.risk_level }];
  }).sort((a, b) => RISK_WEIGHT[b.risk] - RISK_WEIGHT[a.risk] || a.distanceM - b.distanceM).slice(0, limit);
}
export function zoneSummariesAtTime(data: TrackingData, playbackSeconds: number): ZoneSummaryRow[] {
  const minute = playbackSeconds / 60, latest = new Map<string, AnalysisVehicle>(), index = buildAnalysisIndex(data.analysis);
  index.byTrackId.forEach((records, trackId) => { const known = [...records].reverse().find(vehicle => vehicle.capture_min <= minute); if (known) latest.set(trackId, known); });
  index.untracked.forEach(vehicle => { if (vehicle.capture_min <= minute) latest.set(vehicle.vehicle_id, vehicle); });
  const conflicts = new Map<string, number>();
  data.analysis.entities.forEach(entity => entity.reports.forEach(report => { if (report.verdict === 'CONTRADICTED' && clockMinutes(report.time) <= minute) conflicts.set(entity.latest_position.zone, (conflicts.get(entity.latest_position.zone) ?? 0) + 1); }));
  return data.zones.map(zone => {
    const vehicles = [...latest.values()].filter(vehicle => vehicle.zone === zone.name);
    const elevated = vehicles.filter(vehicle => vehicle.risk_level === 'HIGH' || vehicle.risk_level === 'CRITICAL').length;
    return { zone: zone.name, vehicles: vehicles.length, elevated, untracked: vehicles.filter(vehicle => vehicle.track_id === null).length, conflicts: conflicts.get(zone.name) ?? 0, riskScore: vehicles.reduce((sum, vehicle) => sum + RISK_WEIGHT[vehicle.risk_level], 0) };
  });
}
