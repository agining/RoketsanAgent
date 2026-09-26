import { api, mapLimit } from './api';
import type {
  ApiAlert, ApiAssessment, ApiFrameDetail, ApiOffframeRisk, ApiReport, ApiReviewList, ApiRiskCounts, ApiSummary, ApiTrack,
  ApiTrackingData, ApiVehicle,
} from '../types/api';
import {
  toRiskLevel, type AnalysisAlert, type AnalysisData, type AnalysisEntity, type AnalysisFrame, type AnalysisReport,
  type AnalysisVehicle, type OffframeRisk, type RiskCounts, type VehicleType,
} from '../types/analysis';

/** Everything the UI needs, exactly as the API returned it. */
export interface RawAnalysis {
  summary: ApiSummary;
  trackingData: ApiTrackingData;
  frames: ApiFrameDetail[];
  reports: ApiReport[];
  alerts: ApiAlert[];
  assessments: Record<string, ApiAssessment>;
  reviews: ApiReviewList;
  /** /api/tracks/{id} for tracks that no frame vehicle is linked to (their risk lives in `offframe`). */
  offframeTracks: ApiTrack[];
}

const REQUEST_CONCURRENCY = 8;

const isObject = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === 'object' && !Array.isArray(value);
const isNumber = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);
const isString = (value: unknown): value is string => typeof value === 'string';
const isLatLon = (value: unknown) => Array.isArray(value) && value.length === 2 && value.every(isNumber);

/** Runtime boundary: fails loudly with the endpoint name when the API contract changes. */
export function validateRawAnalysis(raw: RawAnalysis): RawAnalysis {
  const { summary, trackingData, frames, reports, alerts } = raw;
  if (!isObject(summary) || !isNumber(summary.generated_at) || !isNumber(summary.frames) || !isObject(summary.frame_risk_counts))
    throw new Error('/api/summary beklenen formatta değil.');
  if (!isObject(trackingData) || !isObject(trackingData.base) || !isString(trackingData.base.name) ||
    !isNumber(trackingData.base.lat) || !isNumber(trackingData.base.lon))
    throw new Error('/api/tracking-data: üs (base) bilgisi eksik.');
  if (!Array.isArray(trackingData.zones) || trackingData.zones.some(zone => !isObject(zone) || !isString(zone.name) || !isLatLon(zone.center)))
    throw new Error('/api/tracking-data: bölge (zones) verisi geçersiz.');
  if (!Array.isArray(trackingData.tracks) || trackingData.tracks.some(track => !isObject(track) || !isString(track.id) ||
    !Array.isArray(track.points) || track.points.some(point => !isString(point.time) || !isNumber(point.lat) || !isNumber(point.lon))))
    throw new Error('/api/tracking-data: iz (tracks) verisi geçersiz.');
  if (!Array.isArray(frames) || frames.some(frame => !isObject(frame) || !isString(frame.frame_id) || !isString(frame.capture_time) ||
    !Array.isArray(frame.vehicles) || frame.vehicles.some(vehicle => !isObject(vehicle) || !isString(vehicle.vehicle_id) ||
      !isNumber(vehicle.lat) || !isNumber(vehicle.lon) || !isString(vehicle.risk_level))))
    throw new Error('/api/frames/{id}: kare/araç verisi geçersiz.');
  if (!Array.isArray(reports) || reports.some(report => !isObject(report) || !isString(report.report_id) || !isString(report.time)))
    throw new Error('/api/reports beklenen formatta değil.');
  if (!Array.isArray(alerts)) throw new Error('/api/alerts beklenen formatta değil.');
  return raw;
}

/** Fetches the full picture from the API. The frontend performs no analysis of its own. */
export async function fetchRawAnalysis(signal?: AbortSignal): Promise<RawAnalysis> {
  const [summary, trackingData, frameList, reports, alerts, assessments, reviews] = await Promise.all([
    api.summary(signal), api.trackingData(signal), api.frames(signal), api.reports(signal), api.alerts('ORTA', signal),
    api.assessments(signal), api.reviews('all', signal),
  ]);
  const frames = await mapLimit(frameList, REQUEST_CONCURRENCY, frame => api.frame(frame.frame_id, signal));
  const linked = new Set(frames.flatMap(frame => frame.vehicles.map(vehicle => vehicle.track_id)).filter(Boolean));
  const unlinked = trackingData.tracks.map(track => track.id).filter(trackId => !linked.has(trackId));
  const offframeTracks = await mapLimit(unlinked, REQUEST_CONCURRENCY, trackId => api.track(trackId, signal));
  return { summary, trackingData, frames, reports, alerts, assessments, reviews, offframeTracks };
}

const VEHICLE_TYPES: readonly VehicleType[] = ['car', 'van', 'truck', 'bus'];
const vehicleType = (label: string | null | undefined): VehicleType => VEHICLE_TYPES.includes(label as VehicleType) ? label as VehicleType : 'unknown';
const riskCounts = (counts: Partial<ApiRiskCounts> | undefined): RiskCounts => ({
  LOW: counts?.DUSUK ?? 0, MEDIUM: counts?.ORTA ?? 0, HIGH: counts?.YUKSEK ?? 0, CRITICAL: counts?.KRITIK ?? 0, UNKNOWN: 0,
});
export const clockMinutes = (clock: string) => { const [hours = 0, minutes = 0] = clock.split(':').map(Number); return hours * 60 + minutes; };
const byTime = <T extends { time: string }>(a: T, b: T) => clockMinutes(a.time) - clockMinutes(b.time);

function vehicleView(vehicle: ApiVehicle): AnalysisVehicle {
  return {
    vehicle_id: vehicle.vehicle_id, frame_id: vehicle.frame_id, capture_time: vehicle.capture_time,
    source: vehicle.source, label: vehicleType(vehicle.label), confidence: vehicle.confidence ?? null, bbox: vehicle.bbox ?? null,
    lat: vehicle.lat, lon: vehicle.lon, zone: vehicle.zone, distance_to_base_m: vehicle.dist_to_base_m,
    bearing_from_base_deg: vehicle.bearing_from_base_deg, track_id: vehicle.track_id, track_match_m: vehicle.track_match_m,
    features: vehicle.features ?? null, filtered: vehicle.filtered, friendly_confirmed_by: vehicle.friendly_confirmed_by ?? [],
    report_ids: vehicle.report_ids ?? [], scenario: vehicle.scenario, risk_reasons: vehicle.risk_reasons ?? [], margin: vehicle.margin ?? null,
    risk_level: toRiskLevel(vehicle.risk_level), engine_risk_level: toRiskLevel(vehicle.engine_risk_level ?? vehicle.risk_level),
    decision_status: vehicle.decision_status ?? 'motor', decision: vehicle.decision ?? null, review: vehicle.review ?? null,
  };
}

function offframeView(risk: ApiOffframeRisk): OffframeRisk {
  return { ...risk, risk_level: toRiskLevel(risk.risk_level), risk_reasons: risk.risk_reasons ?? [], margin: risk.margin ?? null };
}

function reportView(report: ApiReport): AnalysisReport {
  return {
    report_id: report.report_id, time: report.time, source: report.source, text: report.text, verdict: report.verdict,
    report_type: report.report_type, summary: report.summary, matched_vehicle_id: report.matched_vehicle_id ?? null,
    matched_track_id: report.matched_track_id ?? null, related_frames: report.related_frames ?? [], zone: report.zone ?? null,
    checks: report.checks ?? {}, injection_detected: Boolean(report.injection_detected), injection_span: report.injection_span ?? null,
    affects_risk: Boolean(report.affects_risk),
  };
}

function frameView(frame: ApiFrameDetail): AnalysisFrame {
  return {
    frame_id: frame.frame_id, capture_time: frame.capture_time, zone: frame.zone, center: frame.center,
    distance_to_base_m: frame.dist_to_base_m, risk_level: toRiskLevel(frame.risk_level),
    engine_risk_level: toRiskLevel(frame.engine_risk_level ?? frame.risk_level), risk_changed: Boolean(frame.risk_changed),
    counts: riskCounts(frame.counts), pending_reviews: frame.pending_reviews ?? 0, vehicle_ids: frame.vehicle_ids ?? [],
    report_ids: frame.report_ids ?? [], top_vehicle_id: frame.top_vehicle_id ?? null, corner_coordinates: frame.corner_coordinates,
    width_px: frame.width_px, height_px: frame.height_px, pipeline_steps: frame.pipeline_steps ?? [],
  };
}

function alertView(alert: ApiAlert): AnalysisAlert {
  return {
    kind: alert.kind, vehicle_id: alert.vehicle_id, frame_id: alert.frame_id, track_id: alert.track_id, time: alert.time,
    zone: alert.zone, label: alert.label === null ? null : vehicleType(alert.label), risk_level: toRiskLevel(alert.risk_level),
    engine_risk_level: toRiskLevel(alert.engine_risk_level), decision_status: alert.decision_status, scenario: alert.scenario,
    distance_to_base_m: alert.dist_to_base_m, eta_min: alert.eta_min, lat: alert.lat, lon: alert.lon, reason: alert.reason,
  };
}

/** Pure join of API responses into the UI view model (no scoring, no geometry). */
export function buildAnalysis(input: RawAnalysis): AnalysisData {
  const raw = validateRawAnalysis(input);
  const frames = [...raw.frames].sort((a, b) => clockMinutes(a.capture_time) - clockMinutes(b.capture_time) || a.frame_id.localeCompare(b.frame_id));
  const vehicles = frames.flatMap(frame => frame.vehicles.map(vehicleView));
  const vehicleByTrack = new Map(vehicles.filter(vehicle => vehicle.track_id).map(vehicle => [vehicle.track_id as string, vehicle]));
  const offframeByTrack = new Map(raw.offframeTracks.filter(track => track.offframe).map(track => [track.track_id, offframeView(track.offframe as ApiOffframeRisk)]));
  const reports = raw.reports.map(reportView).sort(byTime);

  const entities: AnalysisEntity[] = raw.trackingData.tracks.map(track => {
    const points = [...track.points].sort(byTime);
    const vehicle = vehicleByTrack.get(track.id) ?? null;
    const offframe = vehicle ? null : offframeByTrack.get(track.id) ?? null;
    const evaluated = vehicle ?? offframe;
    return {
      track_id: track.id, points, first_seen: points[0]?.time ?? '', last_seen: points.at(-1)?.time ?? '',
      source: vehicle ? vehicle.source : offframe ? 'offframe' : null,
      vehicle, offframe, vehicle_class: vehicle?.label ?? 'unknown', confidence: vehicle?.confidence ?? null,
      risk_level: evaluated?.risk_level ?? 'UNKNOWN',
      engine_risk_level: vehicle?.engine_risk_level ?? offframe?.risk_level ?? 'UNKNOWN',
      decision_status: vehicle?.decision_status ?? (offframe ? 'motor' : 'bilinmiyor'),
      scenario: evaluated?.scenario ?? null, risk_reasons: evaluated?.risk_reasons ?? [], features: evaluated?.features ?? null,
      observed_at: vehicle?.capture_time ?? offframe?.last_time ?? null, frame_id: vehicle?.frame_id ?? null,
      zone: evaluated?.zone ?? null, distance_to_base_m: vehicle?.distance_to_base_m ?? offframe?.features.dist_now_m ?? null,
      lat: evaluated?.lat ?? null, lon: evaluated?.lon ?? null,
      reports: reports.filter(report => report.matched_track_id === track.id || (vehicle !== null && report.matched_vehicle_id === vehicle.vehicle_id)),
    };
  });

  const summary = raw.summary;
  return {
    generated_at: new Date(summary.generated_at * 1000).toISOString(),
    base: raw.trackingData.base,
    zones: raw.trackingData.zones,
    summary: {
      frames: summary.frames, vehicles: summary.vehicles, tracks: raw.trackingData.tracks.length,
      frame_risk_counts: riskCounts(summary.frame_risk_counts), engine_frame_risk_counts: riskCounts(summary.engine_frame_risk_counts),
      filtered_detections: summary.filtered_detections ?? 0, missed_detections_recovered: summary.missed_detections_recovered ?? 0,
      offframe_tracks: summary.offframe_tracks ?? 0, report_verdicts: summary.report_verdicts ?? {}, decisions: summary.decisions ?? {},
      pending_reviews: summary.pending_reviews ?? 0, assessed_frames: summary.assessed_frames ?? 0,
      llm_enabled: Boolean(summary.llm_enabled), model: summary.model ?? null, detector: summary.detector ?? '',
    },
    human_review: Boolean(summary.human_review),
    entities,
    untracked: vehicles.filter(vehicle => vehicle.track_id === null),
    frames: frames.map(frameView),
    reports,
    alerts: raw.alerts.map(alertView),
    assessments: raw.assessments ?? {},
    reviews: raw.reviews ?? { human_review: Boolean(summary.human_review), items: [], pending_count: 0 },
  };
}

export async function getAnalysis(signal?: AbortSignal): Promise<AnalysisData> {
  return buildAnalysis(await fetchRawAnalysis(signal));
}
