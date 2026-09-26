import { afterEach, describe, expect, it, vi } from 'vitest';
import { api, ApiError, mapLimit } from './api';

afterEach(() => vi.unstubAllGlobals());

describe('api client', () => {
  it('explains a network failure in terms of the API service', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('Failed to fetch'); }));
    await expect(api.summary()).rejects.toThrow("API'ye ulaşılamadı");
  });

  it('treats a non-JSON 5xx (dev proxy) as the API being down', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('', { status: 500, headers: { 'Content-Type': 'text/plain' } })));
    await expect(api.summary()).rejects.toThrow('API yanıt vermedi (/api/summary, HTTP 500)');
  });

  it('surfaces FastAPI error details (e.g. human review disabled → 409)', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Response.json({ detail: 'İnsan onayı kapalı; önce PUT /api/settings ile açın.' }, { status: 409 })));
    let error: ApiError | null = null;
    try { await api.decideReview('img_1_v0', { level: 'ORTA' }); } catch (cause) { error = cause as ApiError; }
    expect(error).toBeInstanceOf(ApiError);
    expect(error?.status).toBe(409);
    expect(error?.message).toContain('İnsan onayı kapalı');
  });

  it('sends the documented request bodies', async () => {
    const fetchMock = vi.fn(async () => Response.json({}));
    vi.stubGlobal('fetch', fetchMock);
    await api.setHumanReview(true);
    await api.decideReview('img_1_v0', { level: 'ORTA', analyst: 'ali', note: null });
    await api.assessFrame('img_1', true);
    await api.assessAll('ORTA');
    const calls = fetchMock.mock.calls as unknown as Array<[string, RequestInit]>;
    expect(calls.map(([url, init]) => `${init.method} ${url} ${init.body ?? ''}`)).toEqual([
      'PUT /api/settings {"human_review":true}',
      'POST /api/reviews/img_1_v0 {"level":"ORTA","analyst":"ali","note":null}',
      'POST /api/frames/img_1/assess?force=true ',
      'POST /api/assess-all {"min_risk":"ORTA","force":false}',
    ]);
  });
});

describe('mapLimit', () => {
  it('keeps order and never exceeds the concurrency limit', async () => {
    let active = 0, peak = 0;
    const result = await mapLimit([1, 2, 3, 4, 5, 6, 7], 3, async value => {
      active++; peak = Math.max(peak, active);
      await new Promise(resolve => setTimeout(resolve, 5));
      active--; return value * 2;
    });
    expect(result).toEqual([2, 4, 6, 8, 10, 12, 14]);
    expect(peak).toBe(3);
  });
});
