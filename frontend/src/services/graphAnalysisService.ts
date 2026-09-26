import type { GraphAnalysis, GraphRegion, ScoreComponent } from '../types/graph';

const object = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === 'object';
const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);
const unit = (value: unknown) => finite(value) && value >= 0 && value <= 1;
const count = (value: unknown) => finite(value) && Number.isInteger(value) && value >= 0;
const strings = (value: unknown) => Array.isArray(value) && value.every(item => typeof item === 'string');
const component = (value: unknown): value is ScoreComponent => object(value) && finite(value.raw) &&
  unit(value.normalized) && unit(value.weight) && unit(value.contribution);

function validRegion(value: unknown): value is GraphRegion {
  if (!object(value) || typeof value.region_id !== 'string' || !object(value.location) ||
      !finite(value.location.lat) || Math.abs(value.location.lat) > 90 ||
      !finite(value.location.lon) || Math.abs(value.location.lon) > 180 ||
      !unit(value.interest_score) || !unit(value.confidence) || !unit(value.local_threat_rate) ||
      !unit(value.global_threat_rate) || !finite(value.threat_lift) || value.threat_lift < 0 ||
      !finite(value.threat_normal_centrality_gap) || !finite(value.radius_m) || value.radius_m <= 0 ||
      !['DUSUK', 'ORTA', 'YUKSEK', 'KRITIK'].includes(String(value.severity)) ||
      typeof value.recommendation !== 'string' || typeof value.representative_node_id !== 'string' ||
      !strings(value.explanation) || !strings(value.member_node_ids) || !strings(value.related_intelligence_ids)) return false;
  for (const key of ['total_vehicle_count', 'threat_vehicle_count', 'normal_vehicle_count',
    'unique_threat_trajectories', 'related_intelligence_count']) if (!count(value[key])) return false;
  if (Number(value.threat_vehicle_count) + Number(value.normal_vehicle_count) !== value.total_vehicle_count) return false;
  const breakdown = value.score_breakdown;
  if (value.vehicle_assessments !== undefined && (!Array.isArray(value.vehicle_assessments) ||
      !value.vehicle_assessments.every(record => object(record) &&
        ['vehicle_id', 'track_id', 'frame_id', 'level', 'reason'].every(key => typeof record[key] === 'string') &&
        strings(record.evidence_report_ids)))) return false;
  if (!unit(value.graph_interest_score) || !unit(value.intelligence_contribution) ||
      !object(breakdown) || !object(breakdown.components) ||
      !Object.values(breakdown.components).every(component) ||
      !['observation_confidence', 'anomaly_evidence', 'multiplier'].every(key => unit(breakdown[key])) ||
      !finite(breakdown.smoothed_lift)) return false;
  if (breakdown.effective_pseudo_count !== undefined &&
      (!finite(breakdown.effective_pseudo_count) || breakdown.effective_pseudo_count < 0)) return false;
  return true;
}

export function validateGraphAnalysis(value: unknown): GraphAnalysis {
  if (!object(value) || value.context !== 'game_simulation' || !finite(value.generated_at) ||
      !unit(value.global_threat_rate) || !unit(value.region_interest_threshold) || typeof value.data_revision !== 'string' ||
      !['analysis_start', 'analysis_end'].every(key => value[key] === null || typeof value[key] === 'string') ||
      !['total_nodes', 'total_edges', 'total_trajectories', 'total_threat_trajectories', 'total_normal_trajectories',
        'region_count', 'high_interest_region_count', 'matched_intelligence_count', 'unmatched_intelligence_count',
        'unclassified_trajectory_count'].every(key => count(value[key])) ||
      !Array.isArray(value.regions) || !value.regions.every(validRegion) ||
      !Array.isArray(value.high_interest_regions) || !value.high_interest_regions.every(validRegion) ||
      value.region_count !== value.regions.length || value.high_interest_region_count !== value.high_interest_regions.length ||
      Number(value.total_threat_trajectories) + Number(value.total_normal_trajectories) !== value.total_trajectories)
    throw new Error('/api/graph-analysis beklenen formatta değil.');
  return value as unknown as GraphAnalysis;
}
