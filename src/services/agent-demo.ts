import type { AnalysisReportView, AnalysisVehicle, RiskLevel } from '../types/analysis';
import type { TrackingData } from '../types/tracking';
import { clockMinutes, currentFrameAtTime, zoneSummariesAtTime } from './operation-summary';
import { reportsAtTime } from './reports';
import { buildAnalysisIndex, RISK_WEIGHT } from './analysis';
import { formatRiskLevel, formatVehicleClass, humanizeAssessmentText } from './formatters';

export type AlertKind = 'critical' | 'contradictions' | 'untracked' | 'missed' | 'manipulation';
export interface AgentAlert { id: string; kind: AlertKind; time: string; title: string; detail: string; risk?: RiskLevel; trackId?: string | null; frameId?: string | null; reportId?: string; lat?: number; lon?: number }

export function alertsAtTime(data: TrackingData, playbackSeconds: number): AgentAlert[] {
  const minute = playbackSeconds / 60, alerts: AgentAlert[] = [];
  const index = buildAnalysisIndex(data.analysis);
  for (const vehicle of [...index.byTrackId.values()].flat()) {
    if (vehicle.capture_min > minute) continue;
    const common = { time: vehicle.capture_time, trackId: vehicle.track_id, frameId: vehicle.frame_id, lat: vehicle.lat, lon: vehicle.lon };
    if (vehicle.risk_level === 'HIGH' || vehicle.risk_level === 'CRITICAL') alerts.push({ id: `risk-${vehicle.vehicle_id}`, kind: 'critical', title: `${vehicle.track_id ?? vehicle.vehicle_id} · ${formatRiskLevel(vehicle.risk_level)}`, detail: humanizeAssessmentText(vehicle.risk_reasons?.[0] ?? vehicle.scenario), risk: vehicle.risk_level, ...common });
    if (vehicle.track_id === null) alerts.push({ id: `untracked-${vehicle.vehicle_id}`, kind: 'untracked', title: `Takipsiz ${formatVehicleClass(vehicle.label)}`, detail: `${vehicle.zone} · üsse ${vehicle.dist_to_base_m.toFixed(0)} m`, risk: vehicle.risk_level, ...common });
    if (vehicle.source === 'track_only') alerts.push({ id: `missed-${vehicle.vehicle_id}`, kind: 'missed', title: `Kaçırılmış tespit · ${vehicle.track_id}`, detail: humanizeAssessmentText(vehicle.risk_reasons?.[0] ?? vehicle.zone), risk: vehicle.risk_level, ...common });
  }
  for (const vehicle of index.untracked) if (vehicle.capture_min <= minute) alerts.push({ id: `untracked-${vehicle.vehicle_id}`, kind: 'untracked', title: `Takipsiz ${formatVehicleClass(vehicle.label)}`, detail: `${vehicle.zone} · üsse ${vehicle.dist_to_base_m.toFixed(0)} m`, risk: vehicle.risk_level, time: vehicle.capture_time, trackId: null, frameId: vehicle.frame_id, lat: vehicle.lat, lon: vehicle.lon });
  for (const report of reportsAtTime(data.analysis, playbackSeconds)) {
    if (report.verdict === 'CONTRADICTED' || report.contradicted_checks > 0) alerts.push(reportAlert(report, 'contradictions', null));
  }
  return alerts.sort((a, b) => (b.risk ? RISK_WEIGHT[b.risk] : b.kind === 'manipulation' ? 5 : 3) - (a.risk ? RISK_WEIGHT[a.risk] : a.kind === 'manipulation' ? 5 : 3) || clockMinutes(b.time) - clockMinutes(a.time));
}
function reportAlert(report: AnalysisReportView, kind: 'contradictions' | 'manipulation', coord: [number, number] | null): AgentAlert {
  return { id: `${kind}-${report.report_id}`, kind, time: report.time, title: `${report.report_id} · ${kind === 'manipulation' ? 'Talimat enjeksiyonu' : 'Rapor çelişkisi'}`, detail: humanizeAssessmentText(report.summary), reportId: report.report_id, trackId: report.matched_track_id, frameId: report.related_frames[0], lat: coord?.[0], lon: coord?.[1] };
}

export function vehicleForCurrentFrame(data: TrackingData, playbackSeconds: number): AnalysisVehicle | null {
  const frame = currentFrameAtTime(data.analysis, playbackSeconds);
  return frame?.vehicles.find(vehicle => vehicle.vehicle_id === frame.top_vehicle_id) ?? null;
}

export function buildSitrep(data: TrackingData, playbackSeconds: number): string {
  const frame = currentFrameAtTime(data.analysis, playbackSeconds), alerts = alertsAtTime(data, playbackSeconds);
  const threats = alerts.filter(alert => alert.kind === 'critical'), conflicts = alerts.filter(alert => alert.kind === 'contradictions'), injections = alerts.filter(alert => alert.kind === 'manipulation');
  const top = threats[0], zones = zoneSummariesAtTime(data, playbackSeconds).sort((a, b) => b.riskScore - a.riskScore);
  const time = new Date(playbackSeconds * 1000).toISOString().slice(11, 16);
  return [`SITREP ${time}: ${frame ? `${frame.zone} bölgesindeki ${frame.frame_id} karesi ${formatRiskLevel(frame.risk_level)} seviyesinde; ${frame.vehicles.length} araç içeriyor.` : 'Zaman imleci yakınında görüntü karesi yok.'}`,
    `${threats.length} yüksek/kritik araç, ${alerts.filter(a => a.kind === 'untracked').length} takipsiz araç ve ${alerts.filter(a => a.kind === 'missed').length} kaçırılmış tespit biliniyor.`,
    top ? `Öncelikli unsur ${top.title}: ${top.detail}` : 'Şu anda öncelikli yüksek riskli unsur yok.',
    `${conflicts.length} çelişen rapor ve ${injections.length} manipülasyon/enjeksiyon uyarısı mevcut. En yoğun bölge: ${zones[0]?.zone ?? 'veri yok'}.`].join(' ');
}

export interface ChatReply { thread_id: string; answer: string; tool_calls?: unknown[] }
export async function sendAgentChat(message: string, threadId?: string, frameId?: string, signal?: AbortSignal): Promise<ChatReply> {
  const configured = ((import.meta.env.VITE_API_URL || import.meta.env.VITE_AGENT_API_URL) as string | undefined)?.replace(/\/$/, '');
  const url = `${configured ?? 'http://localhost:8000'}/api/chat`;
  const response = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message, thread_id: threadId ?? null, frame_id: frameId ?? null }), signal });
  if (!response.ok) throw new Error(response.status === 503 ? 'Agent backend erişilebilir ancak LLM devre dışı.' : `Agent isteği başarısız oldu (HTTP ${response.status}).`);
  return response.json() as Promise<ChatReply>;
}

export function speakText(text: string) {
  if (!('speechSynthesis' in window)) return false;
  window.speechSynthesis.cancel(); const utterance = new SpeechSynthesisUtterance(text); utterance.lang = 'tr-TR'; window.speechSynthesis.speak(utterance); return true;
}
