import type { GraphAnalysis, GraphRegion } from '../../src/types/graph';

export const graphRegion: GraphRegion = {
  region_id: 'REG_N_00001', location: { lat: 39.922, lon: 32.853 }, radius_m: 120,
  interest_score: 0.7, severity: 'YUKSEK', total_vehicle_count: 20, threat_vehicle_count: 8, normal_vehicle_count: 12,
  global_threat_rate: 0.1, local_threat_rate: 0.4, threat_lift: 4, threat_normal_centrality_gap: 0.2,
  unique_threat_trajectories: 8, related_intelligence_count: 0, confidence: 1,
  recommendation: 'Oyun içi gözlem sıklığının artırılması değerlendirilebilir.',
  explanation: ['20 tekil oyun aracı gözlendi.'], related_intelligence_ids: [], member_node_ids: ['N_00001'],
  representative_node_id: 'N_00001', graph_interest_score: 0.7, intelligence_contribution: 0,
  score_breakdown: { observation_confidence: 1, anomaly_evidence: 1, multiplier: 1, smoothed_lift: 3,
    components: { lift: { raw: 3, normalized: 1, weight: 0.7, contribution: 0.7 } } },
};
export const graphSnapshot: GraphAnalysis = {
  context: 'game_simulation', generated_at: 1790380000, total_nodes: 1, total_edges: 0,
  total_trajectories: 80, total_threat_trajectories: 8, total_normal_trajectories: 72, global_threat_rate: 0.1,
  region_count: 1, regions: [graphRegion], high_interest_regions: [graphRegion], high_interest_region_count: 1,
  region_interest_threshold: 0.35,
  matched_intelligence_count: 0, unmatched_intelligence_count: 1, unclassified_trajectory_count: 0,
  analysis_start: '10:00', analysis_end: '12:00', data_revision: 'synthetic-test-revision',
};
