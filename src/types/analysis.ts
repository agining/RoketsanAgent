export const RISK_LEVELS = ['DUSUK', 'ORTA', 'YUKSEK', 'KRITIK'] as const;
export type RiskLevel = typeof RISK_LEVELS[number];
export type VehicleType = 'car' | 'van' | 'truck' | 'bus' | 'unknown';
export type AnalysisSource = 'detection' | 'track_only' | 'offframe';

export interface AnalysisFeatures {
  heading_deg: number | null;
  speed_now_mps: number | null;
  [key: string]: unknown;
}

export interface AnalysisVehicle {
  vehicle_id: string;
  frame_id: string;
  capture_time: string;
  capture_min: number;
  source: AnalysisSource;
  label: VehicleType | null;
  confidence: number | null;
  lat: number;
  lon: number;
  zone: string;
  dist_to_base_m: number;
  track_id: string | null;
  track_match_m: number | null;
  features: AnalysisFeatures | null;
  filtered: boolean;
  scenario: string;
  risk_level: RiskLevel;
  risk_reasons?: string[];
  report_ids?: string[];
}

export interface AnalysisFrame {
  frame_id: string;
  capture_time: string;
  capture_min?: number;
  zone: string;
  risk_level: RiskLevel;
  counts: Record<RiskLevel, number>;
  top_vehicle_id: string | null;
  vehicles: AnalysisVehicle[];
  reports: unknown[];
}

export interface AnalysisData {
  frames: Record<string, AnalysisFrame>;
  offframe_tracks?: Record<string, AnalysisOffframeTrack>;
  reports?: AnalysisReport[];
  summary: AnalysisSummary;
}

export interface AnalysisSummary {
  frames: number;
  frame_risk_counts: Record<RiskLevel, number>;
  vehicles: number;
  missed_detections_recovered: number;
  offframe_tracks: number;
  report_verdicts: Record<string, number>;
}

export interface AnalysisReport {
  report_id: string;
  time: string;
  source: 'official' | 'third_party';
  text: string;
  verdict: ReportVerdict;
  report_type: string;
  summary: string;
  matched_vehicle_id: string | null;
  matched_track_id: string | null;
  zone: string | null;
  related_frames: string[];
  checks: Record<string, unknown>;
  injection_detected: boolean;
  parsed: ParsedClaims;
}

export type ReportVerdict = 'destekler' | 'celisir' | 'kismen_uyumlu' | 'dogrulanamaz' | 'ilgisiz' | 'manipulasyon';

export interface ParsedClaims {
  coord: [number, number] | null;
  zone: string | null;
  types: string[];
  type_word: string | null;
  count: number | null;
  color: string | null;
  claims_stationary: boolean;
  claims_moving: boolean;
  claims_fast: boolean;
  direction_deg: number | null;
  toward_base: boolean;
  claims_normal: boolean;
  zone_traffic_normal: boolean;
  friendly_claim: boolean;
  friendly_confirmed_wording: boolean;
  stale: boolean;
  exercise: boolean;
  injection: boolean;
  injection_span: string | null;
  [key: string]: unknown;
}

export interface AnalysisOffframeTrack {
  track_id: string;
  scenario: string;
  risk_level: RiskLevel;
  last_time: string;
  lat: number;
  lon: number;
  zone: string;
  features: AnalysisFeatures;
  risk_reasons?: string[];
}

export interface AnalysisIndex {
  byTrackId: Map<string, AnalysisVehicle[]>;
  untracked: AnalysisVehicle[];
}
