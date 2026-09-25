import type { AnalysisData, AnalysisFrame, AnalysisVehicle, RiskLevel } from '../types/analysis';
import type { TrackingData } from '../types/tracking';
import { analysisForTrack, buildAnalysisIndex, RISK_WEIGHT, vehicleType } from './analysis';

export interface CriticalVehicleRow {
  trackId: string;
  type: string;
  zone: string;
  distanceM: number;
  scenario: string;
  reason: string;
  risk: RiskLevel;
}

export interface ZoneSummaryRow {
  zone: string;
  vehicles: number;
  elevated: number;
  untracked: number;
  conflicts: number;
  riskScore: number;
}

export const clockMinutes = (clock: string) => {
  const [hours, minutes] = clock.split(':').map(Number);
  return hours * 60 + minutes;
};

export function currentFrameAtTime(analysis: AnalysisData, playbackSeconds: number, toleranceMinutes = 2.5): AnalysisFrame | null {
  const minute = playbackSeconds / 60;
  const candidates = Object.values(analysis.frames).map(frame => ({ frame, distance: Math.abs(clockMinutes(frame.capture_time) - minute) }))
    .filter(candidate => candidate.distance <= toleranceMinutes)
    .sort((a, b) => a.distance - b.distance || RISK_WEIGHT[b.frame.risk_level] - RISK_WEIGHT[a.frame.risk_level]);
  return candidates[0]?.frame ?? null;
}

export function criticalVehiclesAtTime(data: TrackingData, playbackSeconds: number, limit = 6): CriticalVehicleRow[] {
  const index = buildAnalysisIndex(data.analysis);
  return data.tracks.flatMap(track => {
    const vehicle = analysisForTrack(index, track.id, playbackSeconds);
    if (!vehicle || !['YUKSEK', 'KRITIK'].includes(vehicle.risk_level)) return [];
    return [{ trackId: track.id, type: vehicleType(vehicle), zone: vehicle.zone, distanceM: vehicle.dist_to_base_m,
      scenario: vehicle.scenario, reason: vehicle.risk_reasons?.[0] ?? 'No risk reason supplied.', risk: vehicle.risk_level }];
  }).sort((a, b) => RISK_WEIGHT[b.risk] - RISK_WEIGHT[a.risk] || a.distanceM - b.distanceM).slice(0, limit);
}

/** Cumulative latest-known situation at playback time, without exposing future detections. */
export function zoneSummariesAtTime(data: TrackingData, playbackSeconds: number): ZoneSummaryRow[] {
  const minute = playbackSeconds / 60, latest = new Map<string, AnalysisVehicle>(), index = buildAnalysisIndex(data.analysis);
  index.byTrackId.forEach((records, trackId) => { const known = [...records].reverse().find(vehicle => vehicle.capture_min <= minute); if (known) latest.set(trackId, known); });
  index.untracked.forEach(vehicle => { if (vehicle.capture_min <= minute) latest.set(vehicle.vehicle_id, vehicle); });
  const conflicts = new Map<string, number>();
  for (const report of data.analysis.reports ?? []) if (report.verdict === 'celisir' && report.zone && clockMinutes(report.time) <= minute) conflicts.set(report.zone, (conflicts.get(report.zone) ?? 0) + 1);
  return data.zones.map(zone => {
    const vehicles = [...latest.values()].filter(vehicle => vehicle.zone === zone.name);
    const elevated = vehicles.filter(vehicle => vehicle.risk_level === 'YUKSEK' || vehicle.risk_level === 'KRITIK').length;
    return { zone: zone.name, vehicles: vehicles.length, elevated, untracked: vehicles.filter(vehicle => vehicle.track_id === null).length,
      conflicts: conflicts.get(zone.name) ?? 0, riskScore: vehicles.reduce((sum, vehicle) => sum + RISK_WEIGHT[vehicle.risk_level], 0) };
  });
}
