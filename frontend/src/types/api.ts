/**
 * Raw response shapes of the analysis REST API (FastAPI, port 8000).
 * These mirror app/api.py + app/service.py; the UI never reads them directly —
 * services/analysisService.ts turns them into the view model in types/analysis.ts.
 */

export type ApiRiskLevel = 'DUSUK' | 'ORTA' | 'YUKSEK' | 'KRITIK';
export const API_RISK_LEVELS: readonly ApiRiskLevel[] = ['DUSUK', 'ORTA', 'YUKSEK', 'KRITIK'];
export type ApiRiskCounts = Record<ApiRiskLevel, number>;

export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

export interface ApiBase { name: string; lat: number; lon: number }

export interface ApiHealth { status: string; llm_enabled: boolean; detector: string }

export interface ApiSummary {
  frames: number;
  frame_risk_counts: ApiRiskCounts;
  engine_frame_risk_counts: ApiRiskCounts;
  human_review: boolean;
  decisions: Record<string, number>;
  pending_reviews: number;
  vehicles: number;
  filtered_detections: number;
  missed_detections_recovered: number;
  offframe_tracks: number;
  report_verdicts: Record<string, number>;
  assessed_frames: number;
  llm_enabled: boolean;
  model: string | null;
  detector: string;
  /** Unix epoch seconds. */
  generated_at: number;
}

export interface ApiTrackingData {
  base: ApiBase;
  zones: { name: string; center: [number, number] }[];
  tracks: { id: string; points: { time: string; lat: number; lon: number }[] }[];
}

export interface ApiStop { start: string; end: string; minutes: number; lat: number; lon: number; dist_to_base_m: number }

export interface ApiFeatures {
  track_id: string; t_start: string; t_end: string;
  dist_now_m: number; dist_start_m: number; dist_min_m: number; dist_max_m: number;
  approach_total_m: number; approach_last60_m: number | null;
  closing_speed_mps: number; speed_now_mps: number; max_speed_mps: number;
  heading_deg: number | null; bearing_to_base_deg: number; heading_offset_deg: number | null;
  eta_min: number | null;
  stops: ApiStop[]; stops_last60: number; stopped_minutes_total: number; moving_now: boolean;
  path_length_m: number; net_displacement_m: number; extent_m: number;
  radius_cv: number; angular_sweep_deg: number; dist_trend: string; initial_wait_min: number;
}

export interface ApiMargin { confidence: string; can_drop: boolean; can_rise: boolean; rise_to: ApiRiskLevel | null; notes: string[] }

/** Joint engine + LLM decision (agent.py decision table). */
export interface ApiDecision {
  rule: string; rule_label: string;
  engine_level: ApiRiskLevel; llm_level: ApiRiskLevel | null;
  auto_level: ApiRiskLevel; review_level: ApiRiskLevel; needs_review: boolean;
  options?: ApiRiskLevel[]; note?: string | null; llm_reason?: string | null;
  evidence_report_ids?: string[]; motor_confidence?: string; motor_margin_notes?: string[];
}

export interface ApiReview {
  level: ApiRiskLevel; analyst: string; note: string | null;
  /** Unix epoch seconds. */
  at: number;
  frame_id: string; engine_level: ApiRiskLevel; llm_level: ApiRiskLevel | null; rule: string | null;
}

export interface ApiVehicle {
  vehicle_id: string; frame_id: string; capture_time: string; capture_min: number;
  source: 'detection' | 'track_only';
  label: string | null; confidence: number | null; bbox: [number, number, number, number] | null;
  lat: number; lon: number; zone: string; dist_to_base_m: number; bearing_from_base_deg: number;
  track_id: string | null; track_match_m: number | null;
  features: ApiFeatures | null; filtered: boolean; friendly_confirmed_by: string[]; report_ids: string[];
  scenario: string; risk_reasons: string[]; margin: ApiMargin | null;
  /** Final level (engine + LLM joint decision, or analyst decision). */
  risk_level: ApiRiskLevel;
  engine_risk_level: ApiRiskLevel;
  decision_status: string; decision: ApiDecision | null; review: ApiReview | null;
  track_points?: { time: string; lat: number; lon: number }[];
}

export interface ApiFrameListItem {
  frame_id: string; capture_time: string; zone: string;
  risk_level: ApiRiskLevel; engine_risk_level: ApiRiskLevel; risk_changed: boolean;
  pending_reviews: number; counts: ApiRiskCounts; center: [number, number];
  dist_to_base_m: number; n_vehicles: number; report_ids: string[]; assessed: boolean;
}

export interface ApiPipelineStep { step: number; key: string; title: string; summary: string; data?: Record<string, JsonValue> }

export interface ApiReport {
  report_id: string; time: string; source: string; text: string;
  verdict: string; report_type: string; summary: string;
  matched_vehicle_id: string | null; matched_track_id: string | null; related_frames: string[];
  zone: string | null; checks: Record<string, JsonValue>;
  injection_detected: boolean; injection_span: string | null; affects_risk: boolean;
}

export interface ApiReasoningStep { stage: string; finding: string; evidence: string[]; added_by_guardrail?: boolean }
export interface ApiAssessmentVehicle {
  vehicle_id: string; risk_level: ApiRiskLevel; engine_risk_level?: ApiRiskLevel; llm_risk_level?: ApiRiskLevel | null;
  scenario: string; explanation: string; change_reason: string | null; evidence_report_ids: string[];
  decision?: ApiDecision | null; decision_status?: string; review?: ApiReview | null;
}
export interface ApiAssessment {
  frame_id: string; risk_level: ApiRiskLevel; engine_risk_level: ApiRiskLevel; llm_risk_level?: ApiRiskLevel | null;
  headline: string; reasoning_steps: ApiReasoningStep[]; summary: string;
  vehicles: ApiAssessmentVehicle[];
  reports: { report_id: string; verdict: string; explanation: string }[];
  recommended_actions: string[]; injection_report_ids: string[];
  disagreement: string | null; confidence: number; guardrail_notes?: string[];
  model?: string | null; human_review?: boolean; pending_reviews?: number;
  /** Unix epoch seconds. */
  assessed_at?: number;
}

export interface ApiFrameDetail {
  frame_id: string; capture_time: string; capture_min: number; center: [number, number]; zone: string;
  dist_to_base_m: number; vehicle_ids: string[];
  risk_level: ApiRiskLevel; engine_risk_level: ApiRiskLevel; risk_changed: boolean;
  counts: ApiRiskCounts; engine_counts: ApiRiskCounts; pending_reviews: number; human_review: boolean;
  top_vehicle_id: string | null; report_ids: string[];
  corner_coordinates: Record<'top_left' | 'top_right' | 'bottom_left' | 'bottom_right', [number, number]>;
  width_px: number; height_px: number;
  vehicles: ApiVehicle[]; reports: ApiReport[];
  pipeline_steps: ApiPipelineStep[]; assessment: ApiAssessment | null;
}

export interface ApiOffframeRisk {
  track_id: string; scenario: string; risk_level: ApiRiskLevel; risk_reasons: string[]; margin: ApiMargin | null;
  last_time: string; lat: number; lon: number; zone: string; features: ApiFeatures;
}

export interface ApiTrack {
  track_id: string; vehicle_ids: string[]; offframe: ApiOffframeRisk | null;
  points: { time: string; lat: number; lon: number; dist_to_base_m: number }[];
}

export interface ApiAlert {
  kind: 'frame_vehicle' | 'offframe_track';
  vehicle_id: string | null; frame_id: string | null; track_id: string | null;
  time: string; zone: string; label: string | null;
  risk_level: ApiRiskLevel; engine_risk_level: ApiRiskLevel; decision_status: string; scenario: string;
  dist_to_base_m: number; eta_min: number | null; lat: number; lon: number; reason: string; engine_reason: string;
}

export interface ApiSettings { human_review: boolean }

export interface ApiReviewItem {
  vehicle_id: string; frame_id: string; track_id: string | null; zone: string; capture_time: string; label: string | null;
  current_level: ApiRiskLevel; status: string; engine_level: ApiRiskLevel; llm_level: ApiRiskLevel | null;
  rule: string | null; rule_label: string | null; options: ApiRiskLevel[];
  motor: { scenario: string; reasons: string[]; margin: ApiMargin | null };
  llm: { reason: string | null; evidence: { report_id: string; verdict: string; source: string; summary: string }[] };
  note: string | null; review: ApiReview | null;
}
export interface ApiReviewList { human_review: boolean; items: ApiReviewItem[]; pending_count: number }

export interface ApiChatReply { thread_id: string; answer: string; tool_calls?: unknown[]; trace?: unknown[] }
