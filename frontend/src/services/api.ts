import type {
  ApiAlert, ApiAsrStatus, ApiAssessment, ApiChatReply, ApiFrameDetail, ApiGuidePlan, ApiFrameListItem, ApiHealth, ApiReport, ApiReviewList,
  ApiRiskLevel, ApiSettings, ApiSummary, ApiTrack, ApiTrackingData, ApiTranscription,
} from '../types/api';

/**
 * The only transport layer. Every request goes to the analysis API (FastAPI, port 8000).
 *
 * VITE_API_URL empty (default) → relative `/api/...` URLs, forwarded to http://localhost:8000 by the
 * Vite dev/preview proxy (see vite.config.ts; the target can be changed with API_PROXY_TARGET).
 * VITE_API_URL=http://host:8000 → the browser calls the API directly (the API must allow the origin via CORS).
 */
export const API_BASE_URL = ((import.meta.env.VITE_API_URL as string | undefined) ?? '').trim().replace(/\/$/, '');

export class ApiError extends Error {
  constructor(message: string, readonly status: number, readonly path: string) { super(message); this.name = 'ApiError'; }
}

export const apiUrl = (path: string) => `${API_BASE_URL}${path}`;

async function request<T>(path: string, init: RequestInit = {}, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(apiUrl(path), {
      ...init, signal, cache: 'no-store',
      headers: { Accept: 'application/json', ...(init.body ? { 'Content-Type': 'application/json' } : {}), ...init.headers },
    });
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new ApiError(`API'ye ulaşılamadı (${apiUrl(path)}). 8000 portundaki servisin çalıştığını kontrol edin.`, 0, path);
  }
  if (!response.ok) {
    let detail = '';
    let isJson = false;
    try { const body = await response.json() as { detail?: unknown }; isJson = true; detail = typeof body.detail === 'string' ? body.detail : ''; } catch { /* body is not JSON */ }
    // A non-JSON 5xx comes from the dev proxy itself: the API is not running on the proxy target.
    if (!isJson && response.status >= 500) throw new ApiError(`API yanıt vermedi (${path}, HTTP ${response.status}). 8000 portundaki servisin çalıştığını kontrol edin.`, response.status, path);
    throw new ApiError(detail || `API isteği başarısız oldu: ${path} (HTTP ${response.status}).`, response.status, path);
  }
  return response.json() as Promise<T>;
}

const json = (body: unknown): RequestInit => ({ body: JSON.stringify(body) });
const id = encodeURIComponent;

export const api = {
  health: (signal?: AbortSignal) => request<ApiHealth>('/api/health', {}, signal),
  summary: (signal?: AbortSignal) => request<ApiSummary>('/api/summary', {}, signal),
  trackingData: (signal?: AbortSignal) => request<ApiTrackingData>('/api/tracking-data', {}, signal),
  frames: (signal?: AbortSignal) => request<ApiFrameListItem[]>('/api/frames', {}, signal),
  frame: (frameId: string, signal?: AbortSignal) => request<ApiFrameDetail>(`/api/frames/${id(frameId)}?include_tracks=false`, {}, signal),
  track: (trackId: string, signal?: AbortSignal) => request<ApiTrack>(`/api/tracks/${id(trackId)}`, {}, signal),
  reports: (signal?: AbortSignal) => request<ApiReport[]>('/api/reports', {}, signal),
  alerts: (minRisk: ApiRiskLevel = 'ORTA', signal?: AbortSignal) => request<ApiAlert[]>(`/api/alerts?min_risk=${minRisk}`, {}, signal),
  assessments: (signal?: AbortSignal) => request<Record<string, ApiAssessment>>('/api/assessments', {}, signal),
  settings: (signal?: AbortSignal) => request<ApiSettings>('/api/settings', {}, signal),
  reviews: (status: 'pending' | 'decided' | 'all' = 'all', signal?: AbortSignal) => request<ApiReviewList>(`/api/reviews?status=${status}`, {}, signal),

  setHumanReview: (enabled: boolean) => request<ApiSettings & { pending_reviews: number }>('/api/settings', { method: 'PUT', ...json({ human_review: enabled }) }),
  decideReview: (vehicleId: string, body: { level: ApiRiskLevel; analyst?: string | null; note?: string | null }) =>
    request<unknown>(`/api/reviews/${id(vehicleId)}`, { method: 'POST', ...json(body) }),
  undoReview: (vehicleId: string) => request<unknown>(`/api/reviews/${id(vehicleId)}`, { method: 'DELETE' }),
  /** Runs the LLM agent for one frame (cached by the API unless force=true). */
  assessFrame: (frameId: string, force = false) => request<ApiAssessment>(`/api/frames/${id(frameId)}/assess${force ? '?force=true' : ''}`, { method: 'POST' }),
  assessAll: (minRisk: ApiRiskLevel = 'ORTA', force = false) => request<{ assessed: string[] }>('/api/assess-all', { method: 'POST', ...json({ min_risk: minRisk, force }) }),
  chat: (message: string, threadId?: string | null, frameId?: string | null, signal?: AbortSignal) =>
    request<ApiChatReply>('/api/chat', { method: 'POST', ...json({ message, thread_id: threadId ?? null, frame_id: frameId ?? null }) }, signal),
  /** Speech-to-text (Whisper). start loads the model once (slow on first call); transcribe needs it loaded. */
  asrStatus: (signal?: AbortSignal) => request<ApiAsrStatus>('/api/asr/status', {}, signal),
  asrStart: () => request<ApiAsrStatus>('/api/asr/start', { method: 'POST' }),
  asrTranscribe: (audio: Blob, signal?: AbortSignal) =>
    request<ApiTranscription>('/api/asr/transcribe', { method: 'POST', body: audio, headers: { 'Content-Type': audio.type || 'application/octet-stream' } }, signal),
  /** Asks the LLM which UI elements to highlight, in order, for a "how do I…" question (see app/ui_guide.md). */
  uiGuide: (question: string, signal?: AbortSignal) => request<ApiGuidePlan>('/api/ui-guide', { method: 'POST', ...json({ question }) }, signal),
  imageUrl: (frameId: string) => apiUrl(`/api/images/${id(frameId)}`),
};

/** Runs async work with bounded parallelism so a large dataset does not flood the API. */
export async function mapLimit<T, R>(items: readonly T[], limit: number, work: (item: T) => Promise<R>): Promise<R[]> {
  const results = new Array<R>(items.length);
  let next = 0;
  const worker = async () => { while (next < items.length) { const index = next++; results[index] = await work(items[index]); } };
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, worker));
  return results;
}
