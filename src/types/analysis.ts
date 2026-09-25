export const RISK_LEVELS = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL', 'UNKNOWN'] as const;
export type RiskLevel = typeof RISK_LEVELS[number];
export const ATTENTION_LEVELS = ['ROUTINE', 'MONITOR', 'PRIORITY', 'IMMEDIATE', 'UNKNOWN'] as const;
export type AttentionLevel = typeof ATTENTION_LEVELS[number];
export type VehicleType = 'car' | 'van' | 'truck' | 'bus' | 'unknown';
export type MovementState = 'APPROACHING_BASE' | 'LEAVING_BASE' | 'STATIONARY' | 'TRANSIT';
export type BehaviorType = 'NORMAL_PATH' | 'LOITERING' | 'CIRCLING';
export type ReportSource = 'official' | 'third_party';
export type ReportVerdict = 'SUPPORTED' | 'CONTRADICTED' | 'PARTIAL' | 'UNVERIFIED' | 'IRRELEVANT';
export type ReportCheckResult = 'SUPPORTED' | 'CONTRADICTED';

export interface AnalysisBase { name: string; lat: number; lon: number }
/** Zone centers are [latitude, longitude], unlike GeoJSON coordinates. */
export interface AnalysisZone { name: string; center: [number, number] }
export interface RiskCounts extends Record<RiskLevel, number> {}
export interface AttentionCounts extends Record<AttentionLevel, number> {}
export interface CurrentStateCounts {
  approaching_base: number; leaving_base: number; loitering: number; circling: number;
  report_contradiction: number; class_inconsistency: number;
}
export interface PriorityEntity {
  track_id: string; risk_level: RiskLevel; recommended_attention: AttentionLevel; summary: string;
  vehicle_class: VehicleType; zone: string; distance_to_base_m: number;
}
export interface OperationSummary {
  tracked_entity_count: number; untracked_observation_count: number; risk_counts: RiskCounts;
  attention_counts: AttentionCounts; current_state_counts: CurrentStateCounts; priority_entities: PriorityEntity[];
}
export interface VehicleClassSummary {
  canonical: VehicleType;
  observed_classes: Partial<Record<Exclude<VehicleType, 'unknown'>, number>>;
  consistent: boolean;
  average_detection_confidence: number;
}
export interface AnalysisPosition { lat: number; lon: number; zone: string; distance_to_base_m: number }
export interface PositionHistoryEntry extends AnalysisPosition { time: string }
export interface MovementStop { start: string; end: string; minutes: number; lat: number; lon: number }
export interface LatestMovement {
  track_id: string; t_start: string; t_end: string; dist_start_m: number; dist_now_m: number;
  dist_min_m: number; dist_max_m: number; approach_total_m: number; approach_last60_m: number;
  speed_now_mps: number; avg_speed_mps: number; max_speed_mps: number; closing_speed_mps: number;
  heading_deg: number; bearing_to_base_deg: number; heading_offset_deg: number; eta_min: number | null;
  moving_now: boolean; movement_state: MovementState; path_length_m: number; net_displacement_m: number;
  stops: MovementStop[]; stopped_minutes_total: number;
}
export interface MovementHistoryEntry {
  time: string; state: MovementState; speed_mps: number; closing_speed_mps: number;
  eta_min: number | null; distance_to_base_m: number;
}
export interface LatestBehavior {
  track_id: string; behavior: BehaviorType; path_length_m: number; net_displacement_m: number;
  path_efficiency: number; heading_change_total_deg: number; extent_m: number; flags: string[];
}
export interface BehaviorHistoryEntry {
  time: string; behavior: BehaviorType; path_efficiency: number; heading_change_total_deg: number; flags: string[];
}
export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };
export interface ReportCheck { claim: string; result: ReportCheckResult; value: { [key: string]: JsonValue } }
export interface AnalysisReport {
  time: string; source: ReportSource; text: string; report_type: string; vehicle_type: VehicleType;
  matched_track_id: string; match_distance_m: number; verdict: ReportVerdict; supported_checks: number;
  contradicted_checks: number; checks: ReportCheck[]; reasons: string[];
}
export interface ReportSummary { SUPPORTED: number; CONTRADICTED: number; PARTIAL: number; UNVERIFIED: number; IRRELEVANT: number }
export interface RiskAssessment {
  risk_level: RiskLevel; confidence: number; summary: string; reasoning: string[]; key_evidence: string[];
  uncertainties: string[]; recommended_attention: AttentionLevel;
}
export interface EntityRisk { model: string; assessment: RiskAssessment | null; error: string | null }
export interface AnalysisEntity {
  entity_id: string; track_id: string; first_seen: string; last_seen: string; observation_count: number;
  vehicle_class: VehicleClassSummary; latest_position: AnalysisPosition; minimum_distance_to_base_m: number;
  position_history: PositionHistoryEntry[]; latest_movement: LatestMovement; movement_history: MovementHistoryEntry[]; latest_behavior: LatestBehavior | null;
  behavior_history: BehaviorHistoryEntry[]; behavior_flags: string[]; reports: AnalysisReport[];
  report_summary: ReportSummary; current_evidence_flags: string[]; historical_evidence_flags: string[]; risk: EntityRisk;
}
export interface UntrackedDetection {
  class: VehicleType; confidence: number; bbox: [number, number, number, number]; center_pixel: [number, number];
}
export interface UntrackedPosition extends AnalysisPosition {
  zone_center_distance_m: number; bearing_to_base_deg: number; bearing_from_base_deg: number;
}
export interface UntrackedTrackMatch { track_id: null; match_distance_m: null }
export interface UntrackedObservation {
  vehicle_id: string; image_id: string; capture_time: string; detection: UntrackedDetection;
  position: UntrackedPosition; track: UntrackedTrackMatch; movement: LatestMovement | null;
  behavior: LatestBehavior | null; reports: AnalysisReport[]; report_summary: ReportSummary; evidence_flags: string[];
}
/** Exact top-level shape emitted by backend/analysis.json. */
export interface AnalysisData {
  generated_at: string; base: AnalysisBase; zones: AnalysisZone[]; operation_summary: OperationSummary;
  entities: AnalysisEntity[]; untracked_observations: UntrackedObservation[];
}
export type AnalysisStatus = 'idle' | 'loading' | 'success' | 'empty' | 'error';
/** Indexed lookup derived by the frontend; not part of the backend payload. */
export interface AnalysisIndex { byTrackId: Map<string, AnalysisVehicle[]>; untracked: AnalysisVehicle[] }

/** UI projection produced by services/analysis.ts; it is not part of analysis.json. */
export interface AnalysisVehicle {
  vehicle_id: string; frame_id: string; capture_time: string; capture_min: number;
  source: 'detection' | 'track_only'; label: VehicleType | null; confidence: number | null;
  lat: number; lon: number; zone: string; dist_to_base_m: number; track_id: string | null;
  track_match_m: number | null; features: (Partial<LatestMovement> & { dist_trend?: string; stops_last60?: number }) | null;
  filtered: boolean; scenario: string; risk_level: RiskLevel; risk_reasons: string[]; report_ids: string[];
}
export interface AnalysisFrame {
  frame_id: string; capture_time: string; zone: string; risk_level: RiskLevel;
  counts: RiskCounts; top_vehicle_id: string | null; vehicles: AnalysisVehicle[]; reports: AnalysisReportView[];
}
export interface AnalysisReportView extends AnalysisReport {
  report_id: string; zone: string | null; summary: string; related_frames: string[];
  matched_vehicle_id: string | null; injection_detected: false;
}
