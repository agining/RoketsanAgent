# Frontend architecture

The dashboard is a thin client over the analysis API. It never scores risk, validates reports or derives behaviour itself; it joins the API's responses and places them on a map and a timeline.

## Data flow

```
API (FastAPI :8000)
  └─ src/services/api.ts            transport: one function per endpoint, error messages, bounded parallelism
       └─ src/services/analysisService.ts
            fetchRawAnalysis()       summary, tracking-data, frames (+ each frame detail), reports, alerts,
                                     assessments, reviews, and /tracks/{id} for tracks not linked to a frame
            validateRawAnalysis()    runtime contract check, names the failing endpoint
            buildAnalysis()          pure join → AnalysisData (src/types/analysis.ts)
                 └─ src/hooks/useAnalysis.ts   load / reload; keeps the last good data if a refresh fails
                      └─ App.tsx → map, panels, timeline, detail drawer
```

`src/types/api.ts` mirrors the API responses; `src/types/analysis.ts` is the view model the components use.

- **Entity** = one GPS track from `/api/tracking-data`, joined with the frame vehicle the API matched to it (`source: detection` or `track_only` = the detector missed it) or, if no frame shows it, the API's off-frame evaluation (`source: offframe`).
- **Untracked detections** = frame vehicles with `track_id: null`, including low-confidence detections the API filtered out.
- Risk levels map 1:1: `DUSUK→LOW`, `ORTA→MEDIUM`, `YUKSEK→HIGH`, `KRITIK→CRITICAL`; `UNKNOWN` only when the API gave nothing.

After any action (human-review switch, analyst decision, frame assessment) the whole analysis is reloaded from the API, so the UI always shows the API's current final levels. The map camera is kept across reloads.

## Map and playback

- `src/services/analysis-playback.ts` interpolates GPS points between samples for marker movement, builds trail GeoJSON, selected-track events (API stop events, report times, the frame observation) and timeline events (API alerts, their stops, field reports).
- `src/store/playback.ts` + `src/services/playback-clock.ts`: one requestAnimationFrame clock; 1 real second = 1 simulated minute at 1x.
- Markers show the API's final risk level for the track; the detail panel states which observation that level belongs to (frame capture time, or the last track point for off-frame tracks).
- Selecting a track that has not started at the current playback time jumps the clock to its observation.

## Panels

- **Map panel** (`MapSidebar`): layers, filters (risk, vehicle, scenario, zone, search), zone list, untracked detections.
- **Overlays** (`MapOverlays`): operation summary (`/api/summary`) with "assess risky frames" (`/api/assess-all`, `min_risk=ORTA`), priority list (`/api/alerts`), analyst review queue (`/api/reviews`), agent chat (`/api/chat`).
- **All tracks** (`TrackExplorer`): sortable/filterable table of entities.
- **Track detail** (`TrackDetail`): risk decision (final / engine / LLM, rule, engine margin, analyst decision), scenario and reasons, observation with the drone frame and bboxes (`/api/images/{id}`), movement features, agent assessment (run / re-run), interpolated position, field reports with checks, distance history (`/api/tracks/{id}`), engine pipeline steps.
- **Top bar**: last analysis time, track count, high/critical alerts, pending reviews, "Son söz insanda" switch (`PUT /api/settings`), LLM status.

## Game graph replay analysis

The optional graph section in MapSidebar uses `useGraphAnalysis` and the existing API transport. The backend owns all graph calculations. `GraphAnalysisPanel` selects a same-day window and displays a ranked region list, independent graph/report contributions, source references and the representative-node breakdown. `useGraphOverlay` adds a selectable MapLibre layer. Loading/errors remain independent of the main track analysis. See [graph documentation](../../docs/graph-analysis.md) for contracts and formulas.

## Tests

- `src/services/*.test.ts` (Vitest): API client (errors, request bodies, concurrency), API → view-model mapping, playback helpers, formatters.
- `tests/*.spec.ts` (Playwright): the app against a mocked `/api/*` served from `tests/fixtures/api-snapshot.json` (real responses from the synthetic dataset, plus one pending analyst decision).
