import { readFileSync } from 'node:fs';
import type { Page, Route } from '@playwright/test';

/** Snapshot of real API responses (synthetic dataset) + one pending analyst decision. */
export type Snapshot = {
  summary: Record<string, any>; trackingData: { base: any; zones: any[]; tracks: { id: string; points: any[] }[] };
  frames: Array<Record<string, any>>; reports: any[]; alerts: any[]; assessments: Record<string, any>;
  reviews: { human_review: boolean; pending_count: number; items: any[] }; offframeTracks: any[]; tracks: Record<string, any>;
};

export const loadSnapshot = (): Snapshot => JSON.parse(readFileSync(new URL('../fixtures/api-snapshot.json', import.meta.url), 'utf8'));

export interface MockApi { state: Snapshot; calls: Array<{ method: string; path: string; body: unknown }> }

/** Serves every /api/* call from memory, mimicking the FastAPI endpoints the frontend uses. */
export async function mockApi(page: Page, customize?: (state: Snapshot) => void): Promise<MockApi> {
  await page.route(/^https:\/\/tiles\.openfreemap\.org\//, route => route.abort());
  // Existing feature tests start after onboarding; the tutorial is checked separately.
  await page.addInitScript(() => localStorage.setItem('hisar-tutorial-completed', 'true'));
  const state = loadSnapshot();
  customize?.(state);
  const calls: MockApi['calls'] = [];
  await page.route('**/api/**', async (route: Route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname, method = request.method();
    const body = request.postData() ? JSON.parse(request.postData()!) : null;
    calls.push({ method, path, body });
    const json = (data: unknown, status = 200) => route.fulfill({ status, json: data });
    const frame = (id: string) => state.frames.find(item => item.frame_id === id);

    if (method === 'GET' && path === '/api/summary') return json(state.summary);
    if (method === 'GET' && path === '/api/tracking-data') return json(state.trackingData);
    if (method === 'GET' && path === '/api/frames') return json(state.frames.map(({ vehicles, reports, pipeline_steps, assessment, ...rest }) => ({ ...rest, n_vehicles: vehicles.length, assessed: Boolean(state.assessments[rest.frame_id]) })));
    if (method === 'GET' && path.startsWith('/api/frames/')) { const item = frame(decodeURIComponent(path.split('/')[3])); return item ? json(item) : json({ detail: 'bulunamadı' }, 404); }
    if (method === 'GET' && path.startsWith('/api/tracks/')) { const item = state.tracks[decodeURIComponent(path.split('/')[3])]; return item ? json(item) : json({ detail: 'bulunamadı' }, 404); }
    if (method === 'GET' && path === '/api/reports') return json(state.reports);
    if (method === 'GET' && path === '/api/alerts') return json(state.alerts);
    if (method === 'GET' && path === '/api/assessments') return json(state.assessments);
    if (method === 'GET' && path === '/api/reviews') return json({ ...state.reviews, human_review: state.summary.human_review });
    if (method === 'GET' && path.startsWith('/api/images/')) return json({ detail: 'görüntü yok' }, 404);
    if (method === 'PUT' && path === '/api/settings') { state.summary.human_review = body.human_review; return json({ human_review: body.human_review, pending_reviews: state.summary.pending_reviews }); }
    if (method === 'POST' && path.startsWith('/api/reviews/')) {
      if (!state.summary.human_review) return json({ detail: 'İnsan onayı kapalı; önce PUT /api/settings ile açın.' }, 409);
      const item = state.reviews.items.find(entry => entry.vehicle_id === decodeURIComponent(path.split('/')[3]));
      item.review = { level: body.level, analyst: body.analyst ?? 'analist', note: body.note, at: 1790380000, frame_id: item.frame_id, engine_level: item.engine_level, llm_level: item.llm_level, rule: item.rule };
      item.current_level = body.level; item.status = 'analist_karari';
      state.summary.pending_reviews = 0;
      return json({ review: item });
    }
    if (method === 'DELETE' && path.startsWith('/api/reviews/')) {
      const item = state.reviews.items.find(entry => entry.vehicle_id === decodeURIComponent(path.split('/')[3]));
      item.review = null; item.status = 'onay_bekliyor'; state.summary.pending_reviews = 1;
      return json({ vehicle_id: item.vehicle_id });
    }
    if (method === 'POST' && /\/api\/frames\/[^/]+\/assess$/.test(path)) {
      const id = decodeURIComponent(path.split('/')[3]);
      const assessment = { frame_id: id, risk_level: frame(id)?.risk_level, engine_risk_level: frame(id)?.risk_level, llm_risk_level: null, headline: `${id} başlık`, summary: 'Ajan özeti.', reasoning_steps: [{ stage: 'risk', finding: 'Risk bulgusu', evidence: ['T0106'] }], vehicles: [], reports: [], recommended_actions: ['Sürekli izle.'], injection_report_ids: [], disagreement: null, confidence: 0.8, guardrail_notes: [], model: 'test-model', assessed_at: 1790380000 };
      state.assessments[id] = assessment; state.summary.assessed_frames = Object.keys(state.assessments).length;
      return json(assessment);
    }
    if (method === 'POST' && path === '/api/assess-all') return json({ assessed: [] });
    if (method === 'POST' && path === '/api/chat') return json({ thread_id: 't1', answer: `En kritik araç T0106. (${body.frame_id ?? 'bağlamsız'})`, tool_calls: [] });
    return json({ detail: `mock: ${method} ${path}` }, 404);
  });
  return { state, calls };
}
