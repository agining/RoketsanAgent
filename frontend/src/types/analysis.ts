import type {
  ApiAssessment, ApiDecision, ApiFeatures, ApiMargin, ApiPipelineStep, ApiReview, ApiReviewList, ApiRiskLevel, JsonValue,
} from './api';

export type { JsonValue };

/** UI risk scale. API levels map 1:1 (DUSUK→LOW … KRITIK→CRITICAL); UNKNOWN = the API gave no level. */
export const RISK_LEVELS = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL', 'UNKNOWN'] as const;
export type RiskLevel = typeof RISK_LEVELS[number];
export type RiskCounts = Record<RiskLevel, number>;
export type VehicleType = 'car' | 'van' | 'truck' | 'bus' | 'unknown';
export type ObservationSource = 'detection' | 'track_only' | 'offframe';

export interface AnalysisBase { name: string; lat: number; lon: number }
/** Zone centers are [latitude, longitude], unlike GeoJSON coordinates. */
export interface AnalysisZone { name: string; center: [number, number] }
export interface TrackPoint { time: string; lat: number; lon: number }

export interface AnalysisReport {
  report_id: string; time: string; source: string; text: string;
  /** API verdict: destekler | celisir | kismen_uyumlu | dogrulanamaz | ilgisiz | manipulasyon */
  verdict: string; report_type: string; summary: string;
  matched_vehicle_id: string | null; matched_track_id: string | null; related_frames: string[];
  zone: string | null; checks: Record<string, JsonValue>;
  injection_detected: boolean; injection_span: string | null; affects_risk: boolean;
}

/** One vehicle observed in a drone frame (API vehicle_view with final levels). */
export interface AnalysisVehicle {
  vehicle_id: string; frame_id: string; capture_time: string;
  source: 'detection' | 'track_only'; label: VehicleType; confidence: number | null;
  bbox: [number, number, number, number] | null;
  lat: number; lon: number; zone: string; distance_to_base_m: number; bearing_from_base_deg: number;
  track_id: string | null; track_match_m: number | null;
  features: ApiFeatures | null; filtered: boolean; friendly_confirmed_by: string[]; report_ids: string[];
  scenario: string; risk_reasons: string[]; margin: ApiMargin | null;
  /** Final level: engine + LLM joint decision, or the analyst's decision when human review is on. */
  risk_level: RiskLevel; engine_risk_level: RiskLevel;
  decision_status: string; decision: ApiDecision | null; review: ApiReview | null;
}

/** A track that never appears in a frame; the API scores it from the whole track. */
export interface OffframeRisk {
  track_id: string; scenario: string; risk_level: RiskLevel; risk_reasons: string[]; margin: ApiMargin | null;
  last_time: string; lat: number; lon: number; zone: string; features: ApiFeatures;
}

/** One entry per GPS track (tracking-data), joined with the API's analysis of that track. */
export interface AnalysisEntity {
  track_id: string; points: TrackPoint[]; first_seen: string; last_seen: string;
  /** How the API evaluated this track: frame detection, recovered from track (model missed it) or off-frame. */
  source: ObservationSource | null;
  vehicle: AnalysisVehicle | null; offframe: OffframeRisk | null;
  vehicle_class: VehicleType; confidence: number | null;
  risk_level: RiskLevel; engine_risk_level: RiskLevel; decision_status: string;
  scenario: string | null; risk_reasons: string[]; features: ApiFeatures | null;
  /** Time of the evaluated observation (frame capture time, or last track point for off-frame tracks). */
  observed_at: string | null; frame_id: string | null;
  zone: string | null; distance_to_base_m: number | null; lat: number | null; lon: number | null;
  reports: AnalysisReport[];
}

export interface AnalysisFrame {
  frame_id: string; capture_time: string; zone: string; center: [number, number]; distance_to_base_m: number;
  risk_level: RiskLevel; engine_risk_level: RiskLevel; risk_changed: boolean; counts: RiskCounts; pending_reviews: number;
  vehicle_ids: string[]; report_ids: string[]; top_vehicle_id: string | null;
  corner_coordinates: Record<'top_left' | 'top_right' | 'bottom_left' | 'bottom_right', [number, number]>;
  width_px: number; height_px: number; pipeline_steps: ApiPipelineStep[];
}

export interface AnalysisAlert {
  kind: 'frame_vehicle' | 'offframe_track';
  vehicle_id: string | null; frame_id: string | null; track_id: string | null;
  time: string; zone: string; label: VehicleType | null;
  risk_level: RiskLevel; engine_risk_level: RiskLevel; decision_status: string; scenario: string;
  distance_to_base_m: number; eta_min: number | null; lat: number; lon: number; reason: string;
}

export interface OperationSummary {
  frames: number; vehicles: number; tracks: number;
  frame_risk_counts: RiskCounts; engine_frame_risk_counts: RiskCounts;
  filtered_detections: number; missed_detections_recovered: number; offframe_tracks: number;
  report_verdicts: Record<string, number>; decisions: Record<string, number>;
  pending_reviews: number; assessed_frames: number;
  llm_enabled: boolean; model: string | null; detector: string;
}

export interface AnalysisData {
  /** ISO timestamp of the API's last analysis run. */
  generated_at: string;
  base: AnalysisBase; zones: AnalysisZone[];
  summary: OperationSummary; human_review: boolean;
  entities: AnalysisEntity[];
  /** Frame detections without a GPS track (includes low-confidence filtered detections). */
  untracked: AnalysisVehicle[];
  frames: AnalysisFrame[]; reports: AnalysisReport[];
  /** API /alerts (final level ≥ ORTA), highest risk first. */
  alerts: AnalysisAlert[];
  assessments: Record<string, ApiAssessment>;
  reviews: ApiReviewList;
}

export type AnalysisStatus = 'idle' | 'loading' | 'success' | 'empty' | 'error';

export const toRiskLevel = (level: ApiRiskLevel | string | null | undefined): RiskLevel =>
  level === 'DUSUK' ? 'LOW' : level === 'ORTA' ? 'MEDIUM' : level === 'YUKSEK' ? 'HIGH' : level === 'KRITIK' ? 'CRITICAL' : 'UNKNOWN';
export const toApiRiskLevel = (level: RiskLevel): ApiRiskLevel | null =>
  level === 'LOW' ? 'DUSUK' : level === 'MEDIUM' ? 'ORTA' : level === 'HIGH' ? 'YUKSEK' : level === 'CRITICAL' ? 'KRITIK' : null;
