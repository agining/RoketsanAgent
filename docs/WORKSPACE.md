# Atlas operations dashboard

Vehicle-track playback and visualization using React, TypeScript, Vite, Tailwind CSS, shadcn/ui-style Button, Zustand, and MapLibre GL JS.

```sh
npm install
npm run dev
npm run build
npm test
```

Vite imports `mock_data/tracks.csv` and `mock_data/zones.json` as asset URLs (small assets may be inlined). `src/services/tracking.ts` fetches and validates both files and groups CSV rows into `VehicleTrack[]`, preserving point order. The original mock files remain the source of truth.

`src/services/map-data.ts` converts full routes to GeoJSON in longitude/latitude order and calculates bounds. `OperationsMap` owns the map lifecycle and separate route and marker rendering. Zustand holds vehicle selection, layer visibility, and playback state. Clicking a marker, route, or directory entry highlights that vehicle and keeps its live position and bracketing GPS samples in the right inspector.

Zone centers are stored as latitude/longitude pairs and displayed as labeled points. The dataset supplies no zone boundaries. The four layer controls toggle vehicle markers, routes, zones, and the base independently. No backend or LLM functionality is included.

Basemap tiles require internet access to OpenFreeMap; local overlays remain available when tiles fail. The OpenFreeMap dark style is stored in `src/components/map/basemap-style.json`. MapLibre's worker is bundled by Vite. WebGL is required. The map uses the [MapLibre GeoJSON and bounds APIs](https://maplibre.org/maplibre-gl-js/docs/examples/fit-to-the-bounds-of-a-linestring/).

For browser checks, run `npx playwright install chromium --no-shell` followed by `npm run test:e2e`. Node 22+ is recommended to satisfy all dependency engine requirements. Data tests cover validation, grouping, coordinate order, and bounds; the browser test covers rendering, selection, filtering, and mobile overflow.

## Playback

`src/store/playback.ts` stores simulation time in seconds, playing state, speed, and dataset bounds. The bottom timeline supports scrubbing, Play/Pause, jump to beginning, and 1x/5x/15x/60x speed. One real second advances one simulated second at 1x. Playback pauses at the end; Play from the end restarts. Jump to beginning resets and pauses. Hidden browser tabs suspend simulation.

`src/services/playback-clock.ts` uses one requestAnimationFrame loop and elapsed wall time, independent of React renders. `src/services/playback.ts` caches timestamps and uses binary search to locate the surrounding GPS samples. Position is linearly interpolated by the elapsed fraction of that segment. Heading is the initial geographic bearing; approximate speed is haversine distance divided by segment duration, reported in km/h. Stationary segments have no heading. At the final timestamp, heading/speed describe the last segment.

Markers move each animation frame and disappear outside their own recorded intervals, without clearing selection. Direction arrows preserve readable ID labels. Full routes are dim; traveled portions are rendered above them and updated at up to 20 Hz. Selected routes are emphasized. Map instances and markers are retained throughout playback.

HH:mm data has no dates: all vehicles start on the same assumed day; a backwards clock value within a vehicle's source order means midnight rollover. Multi-day tracks whose initial dates differ require dated timestamps to align unambiguously.

Tests cover midpoint and boundary positions, irregular intervals, midnight, stationary/single-point tracks, duplicate timestamps, route clipping, speed changes, seek clamping, and end/reset behavior. Browser checks cover marker movement, persistent selection, pause, scrubbing, layer toggles, and responsive layout.

## Selected vehicle analysis

`src/services/vehicle-metrics.ts` derives base distance (haversine km), cumulative traveled distance including the current partial segment, elapsed tracked duration, cardinal direction, segment speed series, distance series, and recent samples. Cumulative distances and history are cached per track; chart series are memoized. The inspector updates at 10 Hz and chart cursors at one simulated second, independently of full-rate map animation.

Status uses a 0.5 km/h stationary threshold. For moving tracks, distance to base is sampled locally around the simulated position: a radial change beyond ±0.05 km/h is approaching/leaving, otherwise it is steady. These are estimates from interpolated GPS segments. Speed/history use outgoing segment speeds, except the last sample uses the final segment. Charts show the full recorded interval with a current-time cursor; history shows only the five latest samples at or before simulation time. Elapsed time and traveled distance clamp to each vehicle's interval; current position metrics are unavailable outside it.

Follow centers the selected vehicle immediately and on simulation updates, preserving zoom and orientation. It also follows timeline scrubbing. Outside a vehicle's recorded interval, centering is suspended without losing selection. Toggle Follow, drag the map, focus the route, reset the view, or clear selection to stop following. Focus fits the selected full route; Reset fits all dataset tracks and reference locations. These camera actions do not change playback time or play/pause state.

The scrollable inspector uses Recharts for compact distance and speed charts. It stays beside the map on desktop and below the map on narrow screens.

## Map explorer, filters, and controls

`OperationsSidebar` composes `LayerControls`, `VehicleList`, `ZoneList`, and `VehicleFilterPanel`. Search, selected zone, movement states, min/max speed, layer visibility, selection, and sidebar visibility live in `src/store/tracking.ts`. Its setters can be called by future integrations without coupling to the UI.

`src/services/vehicle-filters.ts` is shared by the list and map. Track-ID search is trimmed and case-insensitive. Selected movement states match ANY (OR); search, movement, zone proximity, and speed constraints combine with AND. Speed limits are inclusive in km/h. Empty movement selection means all states. Zone proximity is explicitly **750 m from the supplied center**, not a polygon boundary. Filters reevaluate at 10 Hz of simulated time. With no live filters, completed/upcoming routes remain searchable; markers still only exist visually inside their track's time interval. Filter changes never mutate or discard the original data.

The map hides nonmatching markers and updates traveled/future GeoJSON with matching tracks only. Each segment has its own visibility and click target; the Vehicle routes toggle controls both. Reference zones and base remain independent. Selection stays in the inspector if filtered out; follow centering is suspended until the selected marker is visible again. Clear filters restores membership without changing selection, playback, camera, or layer toggles.

Vehicle rows show current state, speed, and base distance; clicking selects and centers the vehicle, or fits its route outside its recorded interval. Zone focus is separate from the optional Near filter. Hover/focus tooltips show live track ID, speed, movement, and base distance.

The map toolbar fits all original tracks, fits the selected route, resets the camera to north-up overview, toggles the sidebar, and enters/exits native fullscreen (where supported). Fit/reset do not clear filters. Fullscreen can also be exited with Escape. Sidebar tabs support arrow/Home/End keyboard navigation.

## Workspace polish and shortcuts

Both desktop panels resize with drag handles (or focused handle + arrow keys) and collapse independently. Explorer widths are bounded to 210–330 px, inspector widths to 260–400 px, with viewport caps to preserve map space. Selecting a vehicle opens the inspector. The timeline and live status strip stay outside panel scrolling; native fullscreen includes the map, status, and timeline. Desktop layouts are checked at 1366×768 and 1920×1080.

Shortcuts outside text fields and native controls:

- **Space:** play/pause (focused buttons retain their native Space behavior).
- **Left / Right:** pause and step backward/forward by 60 simulated seconds, clamped to dataset bounds.
- **F:** toggle follow for the selected vehicle.
- **Escape:** clear selection; when the command palette is open, closes the palette instead.
- **/**: reveal the explorer, switch to Vehicles, and focus search.
- **Ctrl/Cmd + K:** open/close the command palette.

The shadcn-style Command composition (`src/components/ui/command.tsx`) uses `cmdk` with Radix Dialog for focus trapping, dismissal, and accessible dialog semantics. Commands include vehicle search/selection, focus selected route, fit all, layer toggles, follow, and reset. Selecting a vehicle from the palette clears filters so it can be inspected. Palette portals also work in native fullscreen.

The status strip shows matching active markers (not viewport culling), active filter count, simulated time, speed, selection, and follow/suspended status. Map focus uses a short 380 ms transition; continuous follow remains immediate. Reduced-motion settings disable transitions. Loading, unavailable source files, malformed CSV, invalid zones, empty search results, and empty selection have specific guidance and retry/reset actions.
