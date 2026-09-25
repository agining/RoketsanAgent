import analysisFileUrl from '../../backend/analysis.json?url';
import { ATTENTION_LEVELS, RISK_LEVELS, type AnalysisData } from '../types/analysis';

const isObject = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === 'object' && !Array.isArray(value);
const isNumber = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);
const isString = (value: unknown): value is string => typeof value === 'string';
const isNullableNumber = (value: unknown) => value === null || isNumber(value);
const hasCoordinates = (value: unknown): value is { lat: number; lon: number } => isObject(value) && isNumber(value.lat) && isNumber(value.lon);

/** Runtime boundary for the Python pipeline output. Detailed field types live in types/analysis.ts. */
export function parseAnalysis(value: unknown): AnalysisData {
  if (!isObject(value) || !isString(value.generated_at) || !hasCoordinates(value.base) || !isString((value.base as Record<string, unknown>).name))
    throw new Error('Missing generated_at or valid base data.');
  if (!Array.isArray(value.zones) || value.zones.some(zone => !isObject(zone) || !isString(zone.name) ||
    !Array.isArray(zone.center) || zone.center.length !== 2 || !zone.center.every(isNumber)))
    throw new Error('Invalid zones data.');
  const summary = value.operation_summary;
  const riskCounts = isObject(summary) ? summary.risk_counts : null;
  const attentionCounts = isObject(summary) ? summary.attention_counts : null;
  if (!isObject(summary) || !isNumber(summary.tracked_entity_count) ||
    !isNumber(summary.untracked_observation_count) || !isObject(riskCounts) ||
    RISK_LEVELS.some(level => !isNumber(riskCounts[level])) ||
    !isObject(attentionCounts) || ATTENTION_LEVELS.some(level => !isNumber(attentionCounts[level])) ||
    !isObject(summary.current_state_counts) || !Array.isArray(summary.priority_entities))
    throw new Error('Invalid operation_summary data.');
  const hasAnalysisPosition = (position: unknown) => isObject(position) && hasCoordinates(position) && isString((position as Record<string, unknown>).zone) && isNumber((position as Record<string, unknown>).distance_to_base_m);
  if (!Array.isArray(value.entities) || value.entities.some(entity => !isObject(entity) || !isString(entity.track_id) ||
    !isString(entity.first_seen) || !isString(entity.last_seen) || !isObject(entity.latest_position) ||
    !Array.isArray(entity.position_history) || entity.position_history.some(point => !hasAnalysisPosition(point) || !isString(point.time)) ||
    !isObject(entity.latest_movement) || !isNullableNumber(entity.latest_movement.eta_min) ||
    !(entity.latest_behavior === null || isObject(entity.latest_behavior)) || !Array.isArray(entity.reports) ||
    !isObject(entity.risk) || !(entity.risk.assessment === null || isObject(entity.risk.assessment)) ||
    !(entity.risk.error === null || isString(entity.risk.error))))
    throw new Error('Invalid entities data.');
  if (!Array.isArray(value.untracked_observations) || value.untracked_observations.some(item => !isObject(item) ||
    !isString(item.vehicle_id) || !isString(item.capture_time) || !isObject(item.detection) || !isObject(item.position) ||
    !Array.isArray(item.reports))) throw new Error('Invalid untracked_observations data.');
  return value as unknown as AnalysisData;
}

function analysisUrl(): string {
  const configured = (import.meta.env.VITE_ANALYSIS_URL as string | undefined)?.trim();
  return configured || analysisFileUrl;
}

/** The only transport boundary. Set VITE_ANALYSIS_URL=/api/analysis when the endpoint is available. */
export async function getAnalysis(signal?: AbortSignal): Promise<AnalysisData> {
  let response: Response;
  try { response = await fetch(analysisUrl(), { signal, cache: 'no-store', headers: { Accept: 'application/json' } }); }
  catch (error) { if (signal?.aborted) throw error; throw new Error('Analysis data is unavailable.'); }
  if (!response.ok) throw new Error(`Analysis data is unavailable (HTTP ${response.status}).`);
  try { return parseAnalysis(await response.json()); }
  catch (error) { throw new Error(`Invalid analysis data: ${error instanceof Error ? error.message : 'Cannot read response.'}`); }
}
