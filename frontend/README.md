# Atlas operations dashboard

Frontend-only React + TypeScript + Vite dashboard for the Roketsan field-report agent. **All data and all analysis come from the analysis REST API** (FastAPI, `uvicorn app.api:app --port 8000`). This repository contains no backend, no pipeline and no local data files: the UI fetches the API's results and displays them.

Stack: React 19, TypeScript, Vite 6, Tailwind CSS 4, Zustand, MapLibre GL JS, Recharts.

## Quick start

1. Start the API (in the API project):

   ```sh
   uvicorn app.api:app --reload --port 8000
   ```

   Check it at http://localhost:8000/docs.

2. Start the frontend (in this project):

   ```sh
   npm ci
   npm run dev
   ```

3. Open **http://localhost:5173**.

The browser only talks to the Vite server. Vite forwards every `/api/*` request to `http://localhost:8000`, so no CORS setup is needed.

## Configuration

Copy `.env.example` to `.env.local` if you need to change anything. Restart `npm run dev` after editing it.

| Variable | Default | Purpose |
| --- | --- | --- |
| `API_PROXY_TARGET` | `http://localhost:8000` | Where the dev/preview server forwards `/api/*` |
| `VITE_API_URL` | empty (use the proxy) | Call the API directly from the browser instead, e.g. `http://10.0.0.5:8000`. The API must then allow the page's origin via its `CORS_ORIGINS` setting. Use this for a static `dist/` deployment without the Vite proxy. |

## What comes from which endpoint

| Endpoint | Used for |
| --- | --- |
| `GET /api/summary` | Top bar, operation summary, LLM/detector status, "son analiz" time, human-review state |
| `GET /api/tracking-data` | Base, zones and every GPS track (map playback) |
| `GET /api/frames`, `GET /api/frames/{id}` | Frame vehicles: final/engine risk level, decision status, scenario, reasons, movement features, bbox, engine pipeline steps |
| `GET /api/tracks/{id}` | Off-frame track risk (loaded at start for tracks no frame vehicle is linked to) and per-point distance to base (loaded when a track is opened) |
| `GET /api/reports` | Field reports with the API's verdicts and checks |
| `GET /api/alerts?min_risk=ORTA` | Priority list and timeline risk events |
| `GET /api/assessments` | Cached LLM agent assessments per frame |
| `GET /api/reviews?status=all` | "Son söz insanda" review queue |
| `GET /api/images/{frame_id}` | Drone frame image in the detail panel (hidden when the API returns 404) |
| `PUT /api/settings` | "Son söz insanda" switch in the top bar |
| `POST` / `DELETE /api/reviews/{vehicle_id}` | Analyst decision / undo |
| `POST /api/frames/{id}/assess`, `POST /api/assess-all` | Run the LLM agent for one frame / for all frames at ORTA or above |
| `POST /api/chat` | Agent chat (the selected track's frame is sent as `frame_id`) |

Risk levels are shown exactly as the API returns them (`DUSUK/ORTA/YUKSEK/KRITIK` → Düşük/Orta/Yüksek/Kritik). `risk_level` is the final level (engine + LLM joint decision, or the analyst's decision); `engine_risk_level` and `decision_status` are shown next to it. Without `OPENAI_API_KEY` on the API side, assessments use the engine template and chat returns 503; the UI says so.

## Commands

| Command | Result |
| --- | --- |
| `npm run dev` | Development server at http://localhost:5173 (proxies `/api` to the API) |
| `npm run typecheck` | TypeScript checks |
| `npm test` | Unit tests (API client, API → view-model mapping, playback helpers, formatters) |
| `npm run build` | Type check + production bundle in `dist/` |
| `npm run preview` | Serve `dist/` at http://localhost:4173 (same `/api` proxy) |
| `npm run test:e2e:install` | Download Chromium for browser tests (once per machine) |
| `npm run test:e2e` | Browser tests at http://127.0.0.1:5175 |

Tests do not need a running API: unit and browser tests use `tests/fixtures/api-snapshot.json`, a recorded set of real API responses, and the browser tests serve it through a mocked `/api/*` (`tests/support/mock-api.ts`).

## Prerequisites

- Node.js 22.22.0 (`.nvmrc`) and npm 10. Use `npm ci` with the committed lockfile.
- A browser with WebGL. Basemap tiles come from OpenFreeMap (internet needed; no API key). Markers still render if tiles fail.
- The analysis API running on port 8000 (or wherever `API_PROXY_TARGET` points).

## Troubleshooting

- **"Analiz verisi alınamadı … 8000 portundaki servisin çalıştığını kontrol edin":** the API is not reachable. Start it, check http://localhost:8000/api/health, then press *Tekrar Dene*.
- **"… beklenen formatta değil" with an endpoint name:** the API's response shape changed; `src/services/analysisService.ts` validates the contract and names the failing endpoint.
- **CORS errors:** only happen with `VITE_API_URL` set. Either unset it (use the proxy) or add the page origin to the API's `CORS_ORIGINS`.
- **Port already in use:** dev/preview use strict ports; stop the other process or run `npm run dev -- --port 5174`.
- **Large bundle warning during build:** expected from the map/chart libraries.

See [docs/WORKSPACE.md](docs/WORKSPACE.md) for the frontend architecture.
