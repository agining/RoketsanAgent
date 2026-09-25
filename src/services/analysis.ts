import analysisUrl from '../../mock_data/analysis.json?url';
import { RISK_LEVELS, type AnalysisData, type AnalysisIndex, type AnalysisVehicle, type RiskLevel, type VehicleType } from '../types/analysis';

export const RISK_WEIGHT: Record<RiskLevel, number> = { DUSUK: 1, ORTA: 2, YUKSEK: 3, KRITIK: 4 };

const isObject = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object';
const isNullableNumber = (value: unknown): value is number | null => value === null || (typeof value === 'number' && Number.isFinite(value));

function isAnalysisVehicle(value: unknown): value is AnalysisVehicle {
  if (!isObject(value)) return false;
  return typeof value.vehicle_id === 'string' && typeof value.frame_id === 'string' &&
    typeof value.capture_time === 'string' && typeof value.capture_min === 'number' &&
    (value.source === 'detection' || value.source === 'track_only') &&
    (value.label === null || ['car', 'van', 'truck', 'bus', 'unknown'].includes(String(value.label))) &&
    isNullableNumber(value.confidence) && typeof value.lat === 'number' && typeof value.lon === 'number' && typeof value.zone === 'string' &&
    typeof value.dist_to_base_m === 'number' && (value.track_id === null || typeof value.track_id === 'string') &&
    isNullableNumber(value.track_match_m) && typeof value.filtered === 'boolean' &&
    typeof value.scenario === 'string' && RISK_LEVELS.includes(value.risk_level as RiskLevel);
}

export function parseAnalysisData(value: unknown): AnalysisData {
  if (!isObject(value) || !isObject(value.frames) || !isObject(value.summary)) throw new Error('analysis.json does not contain frames and summary objects.');
  for (const [frameId, frame] of Object.entries(value.frames)) {
    if (!isObject(frame) || frame.frame_id !== frameId || !Array.isArray(frame.vehicles) || !frame.vehicles.every(isAnalysisVehicle)) {
      throw new Error(`analysis.json contains an invalid frame: ${frameId}.`);
    }
  }
  return value as unknown as AnalysisData;
}

export function buildAnalysisIndex(analysis: AnalysisData): AnalysisIndex {
  const byTrackId = new Map<string, AnalysisVehicle[]>(), untracked: AnalysisVehicle[] = [];
  for (const frame of Object.values(analysis.frames)) for (const vehicle of frame.vehicles) {
    if (!vehicle.track_id) { untracked.push(vehicle); continue; }
    const records = byTrackId.get(vehicle.track_id) ?? [];
    records.push(vehicle); byTrackId.set(vehicle.track_id, records);
  }
  for (const record of Object.values(analysis.offframe_tracks ?? {})) {
    const [hours, minutes] = record.last_time.split(':').map(Number);
    const vehicle: AnalysisVehicle = {
      vehicle_id: `offframe_${record.track_id}`, frame_id: '', capture_time: record.last_time,
      capture_min: hours * 60 + minutes, source: 'offframe', label: null, confidence: null,
      lat: record.lat, lon: record.lon, zone: record.zone, dist_to_base_m: Number(record.features.dist_now_m),
      track_id: record.track_id, track_match_m: null, features: record.features, filtered: false,
      scenario: record.scenario, risk_level: record.risk_level, risk_reasons: record.risk_reasons,
    };
    const records = byTrackId.get(record.track_id) ?? [];
    records.push(vehicle); byTrackId.set(record.track_id, records);
  }
  byTrackId.forEach(records => records.sort((a, b) => a.capture_min - b.capture_min));
  untracked.sort((a, b) => a.capture_min - b.capture_min);
  return { byTrackId, untracked };
}

/** Returns the latest analysis snapshot known at the current playback time. */
export function analysisForTrack(index: AnalysisIndex, trackId: string, playbackSeconds: number): AnalysisVehicle | null {
  const records = index.byTrackId.get(trackId);
  if (!records?.length) return null;
  const minute = playbackSeconds / 60;
  for (let index = records.length - 1; index >= 0; index--) if (records[index].capture_min <= minute) return records[index];
  return null;
}

/** Untracked detections are snapshots, so show them only near their capture time. */
export function untrackedAtTime(index: AnalysisIndex, playbackSeconds: number, toleranceMinutes = 2.5): AnalysisVehicle[] {
  const minute = playbackSeconds / 60;
  return index.untracked.filter(vehicle => Math.abs(vehicle.capture_min - minute) <= toleranceMinutes);
}

export function vehicleType(vehicle: AnalysisVehicle | null): VehicleType {
  return vehicle?.source !== 'detection' ? 'unknown' : vehicle.label ?? 'unknown';
}

export async function loadAnalysisData(signal?: AbortSignal): Promise<AnalysisData> {
  let response: Response;
  try { response = await fetch(analysisUrl, { signal }); }
  catch (error) { if (signal?.aborted) throw error; throw new Error('analysis.json unavailable.'); }
  if (!response.ok) throw new Error(`analysis.json unavailable (HTTP ${response.status}).`);
  try { return parseAnalysisData(await response.json()); }
  catch (error) { throw new Error(`Invalid analysis.json: ${error instanceof Error ? error.message : 'Cannot read analysis data.'}`); }
}
