import { useEffect, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import type { Map as LibreMap, StyleSpecification } from 'maplibre-gl';
import type { FeatureCollection, Point } from 'geojson';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import basemapStyle from './basemap-style.json';
import { MapToolbar } from './MapToolbar';
import { filterVehicles, vehicleSnapshot } from '../../services/vehicle-filters';
import type { TrackingData } from '../../types/tracking';
import type { AnalysisVehicle, RiskLevel, VehicleType } from '../../types/analysis';
import { futureFeatures, trackingBounds, traveledFeatures } from '../../services/map-data';
import { useTrackingStore, type MapMode } from '../../store/tracking';
import { usePlaybackStore } from '../../store/playback';
import { getPositionAtTime } from '../../services/playback';
import { analysisForTrack, buildAnalysisIndex, RISK_WEIGHT, untrackedAtTime, vehicleType } from '../../services/analysis';
import { useReportStore } from '../../store/reports';
import { reportsAtTime } from '../../services/reports';
import 'maplibre-gl/dist/maplibre-gl.css';

maplibregl.setWorkerUrl(workerUrl);
const style = basemapStyle as unknown as StyleSpecification;
const riskLevels: RiskLevel[] = ['DUSUK', 'ORTA', 'YUKSEK', 'KRITIK'];
const mapModes: { value: MapMode; label: string }[] = [
  { value: 'vehicle', label: 'Vehicles' }, { value: 'risk', label: 'Risk' }, { value: 'density', label: 'Density' },
];

function vehicleSvg(type: VehicleType): SVGSVGElement {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 28 28'); svg.setAttribute('aria-hidden', 'true');
  const paths: Record<VehicleType, string> = {
    car: '<path d="M6 11l2-4h12l2 4 2 2v7h-3v-2H7v2H4v-7l2-2zm3-2-1.5 4h13L19 9H9zm-1 6a1.5 1.5 0 1 0 0 .01V15zm12 0a1.5 1.5 0 1 0 0 .01V15z"/>',
    van: '<path d="M5 6h13l5 6v9h-3a3 3 0 0 1-6 0h-3a3 3 0 0 1-6 0H3V8a2 2 0 0 1 2-2zm13 3v4h3l-3-4zM8 19a2 2 0 1 0 0 4 2 2 0 0 0 0-4zm9 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4z"/>',
    truck: '<path d="M2 7h14v11h2v-7h4l4 5v5h-2a3 3 0 0 1-6 0H11a3 3 0 0 1-6 0H2V7zm18 6v4h4l-3-4h-1zM8 19a2 2 0 1 0 0 4 2 2 0 0 0 0-4zm13 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4z"/>',
    bus: '<path d="M5 3h18a2 2 0 0 1 2 2v16h-2a3 3 0 0 1-6 0h-6a3 3 0 0 1-6 0H3V5a2 2 0 0 1 2-2zm1 4v7h16V7H6zm2 12a2 2 0 1 0 0 4 2 2 0 0 0 0-4zm12 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4z"/>',
    unknown: '<path d="M14 2l11 12-11 12L3 14 14 2zm-1.5 17h3v-3h-3v3zm.2-5h2.6c.1-1.6 3.2-2 3.2-5 0-2.5-1.9-4-4.5-4-2.4 0-4.1 1.3-4.6 3.6l2.6.7c.3-1.1.9-1.8 2-1.8 1.1 0 1.8.6 1.8 1.6 0 1.8-3.1 2.1-3.1 4.9z"/>',
  };
  svg.innerHTML = paths[type]; return svg;
}

function createVehicleMarker(label: string, tracked = true) {
  const button = document.createElement('button'); button.type = 'button'; button.className = tracked ? 'map-vehicle-marker vehicle-marker' : 'map-vehicle-marker untracked-marker';
  const halo = document.createElement('span'); halo.className = 'risk-halo';
  const glyph = document.createElement('span'); glyph.className = 'vehicle-glyph'; glyph.append(vehicleSvg('unknown'));
  const id = document.createElement('span'); id.className = 'marker-id'; id.textContent = label;
  button.append(halo, glyph, id); return button;
}

function presentMarker(button: HTMLButtonElement, vehicle: AnalysisVehicle | null, mode: MapMode, selected: boolean) {
  const type = vehicleType(vehicle), risk = vehicle?.risk_level;
  button.classList.remove(...riskLevels.map(level => `risk-${level.toLowerCase()}`), 'risk-unknown', 'missed-detection', 'untracked', 'filtered', 'mode-risk', 'selected');
  button.classList.add(risk ? `risk-${risk.toLowerCase()}` : 'risk-unknown');
  button.classList.toggle('missed-detection', vehicle?.source === 'track_only');
  button.classList.toggle('untracked', vehicle?.track_id === null);
  button.classList.toggle('filtered', vehicle?.filtered === true);
  button.classList.toggle('mode-risk', mode === 'risk');
  button.classList.toggle('selected', selected);
  const glyph = button.querySelector<HTMLElement>('.vehicle-glyph');
  if (glyph && glyph.dataset.type !== type) { glyph.replaceChildren(vehicleSvg(type)); glyph.dataset.type = type; }
  button.dataset.risk = risk ?? 'UNKNOWN'; button.dataset.vehicleType = type;
}

function tooltipContent(vehicle: AnalysisVehicle | null, trackId: string | null, speedKmh: number | null, distanceM: number | null) {
  const content = document.createElement('div');
  const title = document.createElement('strong'); title.textContent = vehicle?.vehicle_id ?? trackId ?? 'Unknown vehicle';
  const state = vehicle?.source === 'track_only' ? ' · MISSED DETECTION' : vehicle?.track_id === null ? ' · UNTRACKED' : '';
  const values: [string, string][] = [
    ['Type', vehicleType(vehicle).toUpperCase() + state], ['Track', trackId ?? '—'], ['Risk', vehicle?.risk_level ?? '—'],
    ['Scenario', vehicle?.scenario ?? 'NO ANALYSIS MATCH'], ['Speed', speedKmh == null ? '—' : `${speedKmh.toFixed(1)} km/h`],
    ['Distance', distanceM == null ? '—' : `${(distanceM / 1000).toFixed(2)} km to base`],
    ['Confidence', vehicle?.confidence == null ? '—' : `${Math.round(vehicle.confidence * 100)}%`],
    ['Track match', vehicle?.track_match_m == null ? '—' : `${vehicle.track_match_m.toFixed(1)} m`],
  ];
  content.append(title);
  values.forEach(([label, value]) => { const row = document.createElement('span'); const key = document.createElement('b'); key.textContent = `${label}: `; row.append(key, value); content.append(row); });
  return content;
}

export function OperationsMap({ data }: { data: TrackingData }) {
  const shell = useRef<HTMLDivElement>(null), container = useRef<HTMLDivElement>(null), mapRef = useRef<LibreMap | null>(null);
  const [error, setError] = useState<string | null>(null);
  const mapMode = useTrackingStore(state => state.mapMode);
  useEffect(() => {
    if (!container.current) return;
    let map: LibreMap;
    try { map = new maplibregl.Map({ container: container.current, style, center: [data.base.lon, data.base.lat], zoom: 12, attributionControl: { compact: true } }); }
    catch { setError('The map could not start. Please enable WebGL in your browser.'); return; }
    mapRef.current = map;
    const analysisIndex = buildAnalysisIndex(data.analysis), tracksById = new Map(data.tracks.map(track => [track.id, track]));
    const markers: maplibregl.Marker[] = [], vehicleButtons = new Map<string, HTMLButtonElement>(), vehicleMarkers = new Map<string, maplibregl.Marker>();
    const untrackedButtons = new Map<string, HTMLButtonElement>();
    const reportButtons = new Map<string, HTMLButtonElement>();
    const zoneMarkers: maplibregl.Marker[] = []; let baseMarker: maplibregl.Marker | undefined;
    let lastRouteUpdate = -Infinity, lastFilterTime = -Infinity, lastFilterState = useTrackingStore.getState();
    let matching = data.tracks, visibleIds = new Set(data.tracks.map(track => track.id));
    let hover: { trackId: string | null; vehicle: AnalysisVehicle | null } | null = null;
    const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 24, className: 'vehicle-tooltip' });

    const untrackedMatchesFilters = (vehicle: AnalysisVehicle) => {
      const state = useTrackingStore.getState(), query = state.searchQuery.trim().toLowerCase();
      const speed = (vehicle.features?.speed_now_mps ?? 0) * 3.6;
      return (!query || vehicle.vehicle_id.toLowerCase().includes(query)) && (!state.selectedZone || state.selectedZone === vehicle.zone) &&
        !state.activeMovementStates.length && (state.minSpeed === null || speed >= state.minSpeed) && (state.maxSpeed === null || speed <= state.maxSpeed);
    };
    const currentUntracked = () => untrackedAtTime(analysisIndex, usePlaybackStore.getState().currentTime).filter(untrackedMatchesFilters);
    const updateReportMarkers = () => {
      const reportState = useReportStore.getState(), active = new Set(reportsAtTime(data.analysis, usePlaybackStore.getState().currentTime, reportState).map(report => report.report_id));
      reportButtons.forEach((button, reportId) => { button.style.display = useTrackingStore.getState().layers.reports && active.has(reportId) ? '' : 'none'; button.classList.toggle('selected', reportState.selectedReportId === reportId); });
    };
    const updateTooltip = () => {
      if (!hover || !useTrackingStore.getState().layers.vehicles || useTrackingStore.getState().mapMode === 'density') { popup.remove(); return; }
      if (hover.trackId) {
        if (!visibleIds.has(hover.trackId)) { popup.remove(); return; }
        const track = tracksById.get(hover.trackId), snapshot = track && vehicleSnapshot(track, data, usePlaybackStore.getState().currentTime);
        if (!snapshot?.position) { popup.remove(); return; }
        const vehicle = analysisForTrack(analysisIndex, hover.trackId, usePlaybackStore.getState().currentTime);
        popup.setLngLat([snapshot.position.lon, snapshot.position.lat]).setDOMContent(tooltipContent(vehicle, hover.trackId, vehicle?.features?.speed_now_mps == null ? snapshot.position.speedKmh : vehicle.features.speed_now_mps * 3.6, vehicle?.dist_to_base_m ?? (snapshot.distanceKm == null ? null : snapshot.distanceKm * 1000))).addTo(map);
      } else if (hover.vehicle && currentUntracked().some(vehicle => vehicle.vehicle_id === hover!.vehicle?.vehicle_id)) {
        const vehicle = hover.vehicle;
        popup.setLngLat([vehicle.lon, vehicle.lat]).setDOMContent(tooltipContent(vehicle, null, vehicle.features?.speed_now_mps == null ? null : vehicle.features.speed_now_mps * 3.6, vehicle.dist_to_base_m)).addTo(map);
      } else popup.remove();
    };
    const followSelected = () => {
      const { selectedTrackId, followVehicle, layers } = useTrackingStore.getState();
      if (!followVehicle || !selectedTrackId || !visibleIds.has(selectedTrackId) || !layers.vehicles) return;
      const track = tracksById.get(selectedTrackId), position = track && getPositionAtTime(track, usePlaybackStore.getState().currentTime);
      if (position) { map.stop(); map.jumpTo({ center: [position.lon, position.lat] }); }
    };
    const densityData = (): FeatureCollection<Point> => {
      const time = usePlaybackStore.getState().currentTime;
      const tracked = matching.flatMap(track => {
        const position = getPositionAtTime(track, time); if (!position) return [];
        const analysis = analysisForTrack(analysisIndex, track.id, time);
        return [{ type: 'Feature' as const, properties: { weight: analysis ? RISK_WEIGHT[analysis.risk_level] : 0.1 }, geometry: { type: 'Point' as const, coordinates: [position.lon, position.lat] } }];
      });
      const untracked = currentUntracked().map(vehicle => ({ type: 'Feature' as const, properties: { weight: RISK_WEIGHT[vehicle.risk_level] }, geometry: { type: 'Point' as const, coordinates: [vehicle.lon, vehicle.lat] } }));
      return { type: 'FeatureCollection', features: [...tracked, ...untracked] };
    };
    const updatePositions = (force = false) => {
      const { currentTime, isPlaying } = usePlaybackStore.getState(), state = useTrackingStore.getState(), { layers } = state;
      const filterTime = Math.floor(currentTime * 10) / 10;
      if (force || filterTime !== lastFilterTime || state !== lastFilterState) {
        matching = filterVehicles(data, state, filterTime).map(vehicle => vehicle.track); visibleIds = new Set(matching.map(track => track.id));
        lastFilterTime = filterTime; lastFilterState = state;
      }
      data.tracks.forEach(track => {
        const marker = vehicleMarkers.get(track.id), button = vehicleButtons.get(track.id); if (!marker || !button) return;
        const position = getPositionAtTime(track, currentTime), analysis = analysisForTrack(analysisIndex, track.id, currentTime);
        button.style.display = layers.vehicles && state.mapMode !== 'density' && !!position && visibleIds.has(track.id) ? '' : 'none';
        presentMarker(button, analysis, state.mapMode, state.selectedTrackId === track.id);
        if (!position) return; marker.setLngLat([position.lon, position.lat]);
        const glyph = button.querySelector<HTMLElement>('.vehicle-glyph'), heading = analysis?.features?.heading_deg ?? position.heading;
        if (glyph) { glyph.style.transform = `rotate(${(heading ?? 0) - map.getBearing()}deg)`; glyph.classList.toggle('heading-unknown', heading === null); }
      });
      const activeUntracked = new Set(currentUntracked().map(vehicle => vehicle.vehicle_id));
      analysisIndex.untracked.forEach(vehicle => {
        const button = untrackedButtons.get(vehicle.vehicle_id); if (!button) return;
        button.style.display = layers.vehicles && state.mapMode !== 'density' && activeUntracked.has(vehicle.vehicle_id) ? '' : 'none';
        presentMarker(button, vehicle, state.mapMode, false);
        const glyph = button.querySelector<HTMLElement>('.vehicle-glyph'), heading = vehicle.features?.heading_deg ?? null;
        if (glyph) { glyph.style.transform = `rotate(${(heading ?? 0) - map.getBearing()}deg)`; glyph.classList.toggle('heading-unknown', heading === null); }
      });
      if (map.getLayer('vehicle-density')) map.setLayoutProperty('vehicle-density', 'visibility', layers.vehicles && state.mapMode === 'density' ? 'visible' : 'none');
      updateReportMarkers();
      followSelected();
      const now = performance.now();
      if (force || !isPlaying || now - lastRouteUpdate >= 50) {
        (map.getSource('traveled') as maplibregl.GeoJSONSource | undefined)?.setData(traveledFeatures(matching, currentTime));
        (map.getSource('routes') as maplibregl.GeoJSONSource | undefined)?.setData(futureFeatures(matching, currentTime));
        (map.getSource('vehicle-density') as maplibregl.GeoJSONSource | undefined)?.setData(densityData());
        updateTooltip(); lastRouteUpdate = now;
      }
    };
    const focusDuration = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 380;
    const fit = (duration = focusDuration()) => map.fitBounds(trackingBounds(data), { padding: 65, duration, maxZoom: 15 });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right');
    map.on('error', event => { console.warn('Map resource error:', event.error.message); setError('Some map tiles could not load. Track and zone overlays remain available.'); });
    const select = (id: string) => useTrackingStore.getState().selectTrack(id);
    const applySelection = () => {
      const id = useTrackingStore.getState().selectedTrackId;
      for (const layer of ['selected-route', 'selected-traveled']) if (map.getLayer(layer)) map.setFilter(layer, ['==', ['get', 'trackId'], id ?? '']);
      vehicleButtons.forEach((button, trackId) => { button.classList.toggle('selected', id === trackId); button.setAttribute('aria-pressed', String(id === trackId)); });
    };
    const applyLayers = () => {
      const { layers } = useTrackingStore.getState();
      for (const layer of ['routes', 'selected-route', 'traveled-route', 'selected-traveled', 'route-hit-area', 'traveled-hit-area']) {
        const segmentVisible = layer.includes('traveled') ? layers.traveled : layers.future;
        if (map.getLayer(layer)) map.setLayoutProperty(layer, 'visibility', layers.routes && segmentVisible ? 'visible' : 'none');
      }
      zoneMarkers.forEach(marker => { marker.getElement().style.display = layers.zones ? '' : 'none'; });
      if (baseMarker) baseMarker.getElement().style.display = layers.base ? '' : 'none'; updatePositions(true);
    };
    const unsubscribe = useTrackingStore.subscribe((state, old) => {
      if (state.selectedTrackId !== old.selectedTrackId) applySelection();
      if (state.layers !== old.layers) applyLayers();
      if (state.mapMode !== old.mapMode || state.searchQuery !== old.searchQuery || state.selectedZone !== old.selectedZone || state.activeMovementStates !== old.activeMovementStates || state.minSpeed !== old.minSpeed || state.maxSpeed !== old.maxSpeed) updatePositions(true);
      if (state.followVehicle !== old.followVehicle || state.selectedTrackId !== old.selectedTrackId) followSelected();
      if (state.viewRequest !== old.viewRequest) {
        if (state.viewRequest.action === 'reset' || state.viewRequest.action === 'all') { if (state.viewRequest.action === 'reset') map.jumpTo({ bearing: 0, pitch: 0 }); fit(); }
        else if (state.viewRequest.action === 'zone') { const zone = data.zones.find(zone => zone.name === state.viewRequest.zoneName); if (zone) map.easeTo({ center: [zone.center[1], zone.center[0]], zoom: 14, duration: focusDuration() }); }
        else if (state.viewRequest.action === 'coordinate' && state.viewRequest.coordinate) map.easeTo({ center: state.viewRequest.coordinate, zoom: Math.max(map.getZoom(), 14), duration: focusDuration() });
        else { const track = state.selectedTrackId ? tracksById.get(state.selectedTrackId) : undefined, position = track && getPositionAtTime(track, usePlaybackStore.getState().currentTime);
          if (state.viewRequest.action === 'vehicle' && position) map.easeTo({ center: [position.lon, position.lat], zoom: Math.max(map.getZoom(), 14), duration: focusDuration() });
          else if (track?.points.length) { const bounds = new maplibregl.LngLatBounds(); track.points.forEach(point => bounds.extend([point.lon, point.lat])); map.fitBounds(bounds, { padding: 65, duration: focusDuration(), maxZoom: 16 }); }
        }
      }
    });
    const unsubscribePlayback = usePlaybackStore.subscribe((state, old) => { if (state.currentTime !== old.currentTime || state.isPlaying !== old.isPlaying) updatePositions(); });
    const unsubscribeReports = useReportStore.subscribe(updateReportMarkers);
    map.on('dragstart', () => useTrackingStore.getState().setFollowVehicle(false)); map.on('rotate', () => updatePositions());
    map.on('style.load', () => {
      map.addSource('vehicle-density', { type: 'geojson', data: densityData() });
      map.addLayer({ id: 'vehicle-density', type: 'heatmap', source: 'vehicle-density', layout: { visibility: 'none' }, paint: {
        'heatmap-weight': ['interpolate', ['linear'], ['get', 'weight'], 1, 0.2, 4, 1], 'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 9, 0.8, 15, 2.4],
        'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 9, 14, 15, 34], 'heatmap-opacity': 0.82,
        'heatmap-color': ['interpolate', ['linear'], ['heatmap-density'], 0, 'rgba(24,40,48,0)', 0.2, '#5d9f82', 0.45, '#d5b84b', 0.7, '#ef7a3d', 1, '#ef3340'],
      } });
      map.addSource('routes', { type: 'geojson', data: futureFeatures(matching, usePlaybackStore.getState().currentTime) });
      map.addLayer({ id: 'routes', type: 'line', source: 'routes', layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': '#739da5', 'line-width': 2, 'line-opacity': 0.22 } });
      map.addLayer({ id: 'selected-route', type: 'line', source: 'routes', filter: ['==', ['get', 'trackId'], ''], layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': '#8ee3c0', 'line-width': 3, 'line-opacity': 0.4 } });
      map.addSource('traveled', { type: 'geojson', data: traveledFeatures(data.tracks, usePlaybackStore.getState().currentTime) });
      map.addLayer({ id: 'traveled-route', type: 'line', source: 'traveled', layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': '#83afb5', 'line-width': 2.5, 'line-opacity': 0.9 } });
      map.addLayer({ id: 'selected-traveled', type: 'line', source: 'traveled', filter: ['==', ['get', 'trackId'], ''], layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': '#a2e5c8', 'line-width': 4, 'line-opacity': 1 } });
      map.addLayer({ id: 'route-hit-area', type: 'line', source: 'routes', paint: { 'line-width': 14, 'line-opacity': 0 } });
      map.addLayer({ id: 'traveled-hit-area', type: 'line', source: 'traveled', paint: { 'line-width': 14, 'line-opacity': 0 } });
      for (const hitLayer of ['route-hit-area', 'traveled-hit-area']) { map.on('click', hitLayer, event => { const id = event.features?.[0]?.properties?.trackId; if (typeof id === 'string') select(id); }); map.on('mouseenter', hitLayer, () => { map.getCanvas().style.cursor = 'pointer'; }); map.on('mouseleave', hitLayer, () => { map.getCanvas().style.cursor = ''; }); }
      data.zones.forEach(zone => { const element = document.createElement('button'); element.type = 'button'; element.className = 'zone-marker'; element.setAttribute('aria-label', `Focus map zone ${zone.name}`); element.title = `${zone.name} · Zone center`; element.addEventListener('click', event => { event.stopPropagation(); useTrackingStore.getState().requestView('zone', zone.name); }); const dot = document.createElement('i'), label = document.createElement('span'); label.textContent = zone.name; element.append(dot, label); const marker = new maplibregl.Marker({ element }).setLngLat([zone.center[1], zone.center[0]]).addTo(map); zoneMarkers.push(marker); markers.push(marker); });
      const base = document.createElement('div'); base.className = 'base-marker'; const baseIcon = document.createElement('span'); baseIcon.textContent = '⌂'; const baseLabel = document.createElement('strong'); baseLabel.textContent = data.base.name; base.append(baseIcon, baseLabel); baseMarker = new maplibregl.Marker({ element: base }).setLngLat([data.base.lon, data.base.lat]).addTo(map); markers.push(baseMarker);
      (data.analysis.reports ?? []).forEach(report => { if (!report.parsed.coord) return; const button = document.createElement('button'); button.type = 'button'; button.className = `report-map-marker verdict-${report.verdict}`; button.textContent = report.injection_detected ? '⚠' : '!'; button.title = `${report.report_id} · ${report.verdict} · ${report.time}`; button.setAttribute('aria-label', `Select report ${report.report_id}`); button.addEventListener('click', event => { event.stopPropagation(); useReportStore.getState().selectReport(report.report_id); }); reportButtons.set(report.report_id, button); const marker = new maplibregl.Marker({ element: button }).setLngLat([report.parsed.coord[1], report.parsed.coord[0]]).addTo(map); markers.push(marker); });
      data.tracks.forEach(track => { const point = track.points[0]; if (!point) return; const button = createVehicleMarker(track.id); button.setAttribute('aria-label', `Select vehicle ${track.id}`); const showTooltip = () => { hover = { trackId: track.id, vehicle: null }; updateTooltip(); }, hideTooltip = () => { hover = null; popup.remove(); }; button.addEventListener('mouseenter', showTooltip); button.addEventListener('focus', showTooltip); button.addEventListener('mouseleave', hideTooltip); button.addEventListener('blur', hideTooltip); button.addEventListener('click', event => { event.stopPropagation(); select(track.id); }); vehicleButtons.set(track.id, button); const marker = new maplibregl.Marker({ element: button }).setLngLat([point.lon, point.lat]).addTo(map); vehicleMarkers.set(track.id, marker); markers.push(marker); });
      analysisIndex.untracked.forEach(vehicle => { const button = createVehicleMarker('!', false); button.setAttribute('aria-label', `Untracked ${vehicle.label ?? 'vehicle'} ${vehicle.vehicle_id}`); const showTooltip = () => { hover = { trackId: null, vehicle }; updateTooltip(); }, hideTooltip = () => { hover = null; popup.remove(); }; button.addEventListener('mouseenter', showTooltip); button.addEventListener('focus', showTooltip); button.addEventListener('mouseleave', hideTooltip); button.addEventListener('blur', hideTooltip); untrackedButtons.set(vehicle.vehicle_id, button); const marker = new maplibregl.Marker({ element: button }).setLngLat([vehicle.lon, vehicle.lat]).addTo(map); markers.push(marker); });
      applySelection(); applyLayers(); fit(0);
    });
    const observer = new ResizeObserver(() => map.resize()); observer.observe(container.current);
    return () => { unsubscribe(); unsubscribePlayback(); unsubscribeReports(); observer.disconnect(); popup.remove(); markers.forEach(marker => marker.remove()); map.remove(); mapRef.current = null; };
  }, [data]);
  return <div className="map-shell" ref={shell}><div ref={container} className="map-canvas" aria-label="Vehicle operations map" /><MapToolbar target={shell} />
    <div className="map-mode-switch" role="group" aria-label="Map visualization mode">{mapModes.map(mode => <button key={mode.value} aria-pressed={mapMode === mode.value} onClick={() => useTrackingStore.getState().setMapMode(mode.value)}>{mode.label}</button>)}</div>
    {error && <div role="status" className="map-error">{error}</div>}
    <div className="map-legend risk-legend"><span><i className="legend-route" />Traveled</span><span><i className="legend-route future" />Future</span>{riskLevels.map(level => <span key={level}><i className={`legend-risk risk-${level.toLowerCase()}`} />{level}</span>)}</div>
  </div>;
}
