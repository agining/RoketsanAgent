import type { AnalysisData, AnalysisEntity, AnalysisIndex, AnalysisVehicle, RiskLevel, UntrackedObservation, VehicleType } from '../types/analysis';
import { formatEvidenceFlag } from './formatters';

export const RISK_WEIGHT: Record<RiskLevel, number> = { UNKNOWN: 0, LOW: 1, MEDIUM: 2, HIGH: 3, CRITICAL: 4 };
export const clockMinutes = (clock: string) => { const [hours, minutes] = clock.split(':').map(Number); return hours * 60 + minutes; };

export function buildAnalysisIndex(analysis: AnalysisData): AnalysisIndex {
  return {
    byTrackId: new Map(analysis.entities.map(entity => [entity.track_id, [entityVehicle(entity)]])),
    untracked: analysis.untracked_observations.map(untrackedVehicle),
  };
}
/** Returns an entity only after its first observation at the playback cursor. */
export function analysisForTrack(index: AnalysisIndex, trackId: string, playbackSeconds: number): AnalysisVehicle | null {
  const vehicle = index.byTrackId.get(trackId)?.[0] ?? null;
  return vehicle && vehicle.capture_min <= playbackSeconds / 60 ? vehicle : null;
}
export function untrackedAtTime(index: AnalysisIndex, playbackSeconds: number, toleranceMinutes = 2.5): AnalysisVehicle[] {
  const minute = playbackSeconds / 60;
  return index.untracked.filter(item => Math.abs(clockMinutes(item.capture_time) - minute) <= toleranceMinutes);
}
export function vehicleType(item: AnalysisVehicle | AnalysisEntity | UntrackedObservation | null): VehicleType {
  if (!item) return 'unknown';
  if ('label' in item) return item.label ?? 'unknown';
  return 'entity_id' in item ? item.vehicle_class.canonical : item.detection.class;
}
export function entityRisk(entity: AnalysisEntity | null): RiskLevel { return entity?.risk.assessment?.risk_level ?? 'UNKNOWN'; }

function entityVehicle(entity: AnalysisEntity): AnalysisVehicle {
  const assessment = entity.risk.assessment;
  return {
    vehicle_id: entity.entity_id, frame_id: '', capture_time: entity.first_seen, capture_min: clockMinutes(entity.first_seen),
    source: 'detection', label: entity.vehicle_class.canonical, confidence: entity.vehicle_class.average_detection_confidence,
    lat: entity.latest_position.lat, lon: entity.latest_position.lon, zone: entity.latest_position.zone,
    dist_to_base_m: entity.latest_position.distance_to_base_m, track_id: entity.track_id, track_match_m: null,
    features: { ...entity.latest_movement, dist_trend: entity.latest_movement.movement_state }, filtered: false,
    scenario: entity.latest_behavior?.behavior ?? entity.latest_movement.movement_state,
    risk_level: assessment?.risk_level ?? 'UNKNOWN', risk_reasons: assessment?.reasoning ?? [entity.risk.error ?? 'Risk değerlendirmesi mevcut değil.'],
    report_ids: entity.reports.map((report, index) => reportId(report.matched_track_id, report.time, index)),
  };
}

function untrackedVehicle(item: UntrackedObservation): AnalysisVehicle {
  return {
    vehicle_id: item.vehicle_id, frame_id: item.image_id, capture_time: item.capture_time, capture_min: clockMinutes(item.capture_time),
    source: 'detection', label: item.detection.class, confidence: item.detection.confidence,
    lat: item.position.lat, lon: item.position.lon, zone: item.position.zone, dist_to_base_m: item.position.distance_to_base_m,
    track_id: null, track_match_m: null, features: item.movement, filtered: false, scenario: item.behavior?.behavior ?? 'Takipsiz tespit',
    risk_level: 'UNKNOWN', risk_reasons: item.evidence_flags.map(formatEvidenceFlag), report_ids: [],
  };
}

export const reportId = (trackId: string, time: string, index: number) => `${trackId}-${time.replace(':', '')}-${index + 1}`;
