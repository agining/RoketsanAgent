export interface GraphWindow { start_time?: string; end_time?: string }
export interface VehicleFeedback {
  vehicle_id: string; track_id: string; frame_id: string; capture_time: string | null;
  level: string; status: string | null; reason: string; evidence_report_ids: string[];
  review: Record<string, unknown> | null;
}
export interface VehicleSummary {
  region_id: string; method: 'llm' | 'stored_feedback' | 'stored_feedback_fallback';
  findings: { text: string; vehicle_ids: string[] }[]; vehicle_count: number; track_count: number;
}
export interface ScoreComponent { raw: number; normalized: number; weight: number; contribution: number }
export interface ScoreBreakdown {
  components: Record<string, ScoreComponent>;
  observation_confidence: number;
  anomaly_evidence: number;
  multiplier: number;
  smoothed_lift: number;
  effective_pseudo_count?: number;
  group_rule?: { matched: boolean; distinct_threat_tracks: number; local_threat_ratio: number;
    minimum_tracks: number; high_tracks: number; minimum_ratio: number; base_score: number; score_cap_applied: boolean };
}
export interface GraphRegion {
  region_id: string;
  location: { lat: number; lon: number };
  radius_m: number;
  interest_score: number;
  severity: 'DUSUK' | 'ORTA' | 'YUKSEK' | 'KRITIK';
  total_vehicle_count: number;
  threat_vehicle_count: number;
  normal_vehicle_count: number;
  global_threat_rate: number;
  local_threat_rate: number;
  threat_lift: number;
  threat_normal_centrality_gap: number;
  unique_threat_trajectories: number;
  related_intelligence_count: number;
  confidence: number;
  recommendation: string;
  explanation: string[];
  related_intelligence_ids: string[];
  member_node_ids: string[];
  representative_node_id: string;
  graph_interest_score: number;
  intelligence_contribution: number;
  score_breakdown: ScoreBreakdown;
  vehicle_assessments?: VehicleFeedback[];
}
export interface GraphAnalysis {
  context: 'game_simulation';
  generated_at: number;
  total_nodes: number;
  total_edges: number;
  total_trajectories: number;
  total_threat_trajectories: number;
  total_normal_trajectories: number;
  global_threat_rate: number;
  region_count: number;
  regions: GraphRegion[];
  high_interest_regions: GraphRegion[];
  high_interest_region_count: number;
  region_interest_threshold: number;
  matched_intelligence_count: number;
  unmatched_intelligence_count: number;
  unclassified_trajectory_count: number;
  analysis_start: string | null;
  analysis_end: string | null;
  data_revision: string;
}
