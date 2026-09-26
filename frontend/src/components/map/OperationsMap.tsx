import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react';
import { Box, Focus, GripVertical, Info, LocateFixed, Maximize, Minimize, RotateCcw } from 'lucide-react';
import * as maplibregl from 'maplibre-gl';
import type { ExpressionSpecification, GeoJSONSource, Map as LibreMap, Marker, StyleSpecification } from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import basemapStyle from './basemap-style.json';
import { Button } from '../ui/button';
import { useTrackingStore } from '../../store/tracking';
import { usePlaybackStore } from '../../store/playback';
import type { AnalysisData, AnalysisEntity, AnalysisVehicle, RiskLevel } from '../../types/analysis';
import { allTrackTrailFeatures, formatClock, headingAtTime, positionAtTime, reportsAtTime, selectedTrackEventFeatures, trackColor, trailArrowFeatures, untrackedVisibleAt } from '../../services/analysis-playback';
import type { TrailMode } from '../../store/playback';
import { formatDecisionStatus, formatMeters, formatPercent, formatRiskLevel, formatScenario, formatSource, formatUnavailable, formatVehicleClass } from '../../services/formatters';
import { activeTrackEntities } from '../../services/trackFilters';
import 'maplibre-gl/dist/maplibre-gl.css';

maplibregl.setWorkerUrl(workerUrl);
const style = basemapStyle as unknown as StyleSpecification;
const visualControlsStorageKey = 'hisar-map-visual-controls-position-v1';
const vehicleMarkerZoom = {
  mid: 13.25,
  label: 14.75,
} as const;
/** Change paint only: theme switches preserve camera, selection, sources and playback. */
function applyMapTheme(map: LibreMap) {
  const light = document.documentElement.dataset.theme === 'light';
  for (const layer of style.layers) {
    if (!map.getLayer(layer.id) || !('paint' in layer) || !layer.paint) continue;
    for (const [property, original] of Object.entries(layer.paint)) {
      if (!property.endsWith('-color')) continue;
      let value = original;
      if (light) {
        const id = layer.id;
        if (property === 'text-halo-color') value = '#f8faf9';
        else if (property === 'text-color') value = id.includes('water') ? '#477888' : '#647887';
        else if (layer.type === 'background') value = '#eaf0f2';
        else if (id.includes('water')) value = '#bddbe3';
        else if (id.includes('wood') || id.includes('park')) value = '#d5e5da';
        else if (id.includes('ice') || id.includes('glacier')) value = '#f5fafb';
        else if (id.includes('building')) value = '#d9e2e7';
        else if (id.includes('residential')) value = '#e4ebef';
        else if (id.includes('boundary')) value = '#aebfc8';
        else if (id.includes('railway')) value = id.includes('dash') ? '#edf2f4' : '#bac9d1';
        else if (id.includes('casing')) value = '#cedae1';
        else if (id.includes('motorway')) value = '#f5ecd7';
        else if (layer.type === 'line') value = '#ffffff';
        else value = '#e1e9ed';
      }
      map.setPaintProperty(layer.id, property as Parameters<LibreMap['setPaintProperty']>[1], value);
    }
  }
  const paints: [string, string, string, string][] = [
    ['all-track-trails-casing', 'line-color', '#ffffff', '#061015'],
    ['trail-arrows', 'text-halo-color', '#ffffff', '#071015'],
    ['selected-track-events', 'circle-stroke-color', '#ffffff', '#101a20'],
    ['operational-3d-buildings', 'fill-extrusion-color', '#b7c9d2', '#25333a'],
  ];
  for (const [id, property, day, night] of paints) {
    if (map.getLayer(id)) map.setPaintProperty(id, property as Parameters<LibreMap['setPaintProperty']>[1], light ? day : night);
  }
  // A darker version of the existing trail palette remains legible on the light basemap.
  const trailColor: ExpressionSpecification = light ? ['match', ['get', 'color'],
    '#9ed0bd', '#16796a', '#d5b96f', '#976d1b', '#82aac8', '#336f9c', '#c98572', '#ab5b42',
    '#b895d6', '#8159a6', '#7fc7c0', '#257f89', '#e0a36f', '#ac6928', '#a7bd78', '#647c2c', '#337c71'] : ['get', 'color'];
  if (map.getLayer('all-track-trails')) map.setPaintProperty('all-track-trails', 'line-color', trailColor);
  if (map.getLayer('trail-arrows')) map.setPaintProperty('trail-arrows', 'text-color', trailColor);
}

const riskLevels: RiskLevel[] = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL', 'UNKNOWN'];
const riskGlyph: Record<RiskLevel, string> = { LOW: 'D', MEDIUM: 'O', HIGH: 'Y', CRITICAL: 'K', UNKNOWN: '?' };

function valueRow(label: string, value: string) {
  const row = document.createElement('span');
  const key = document.createElement('small');
  const content = document.createElement('b');
  key.textContent = label;
  content.textContent = value;
  row.append(key, content);
  return row;
}

function trackPopup(entity: AnalysisEntity, time: number) {
  const position = positionAtTime(entity, time);
  const reports = reportsAtTime(entity, time);
  const content = document.createElement('div');
  content.className = 'analysis-map-popup';
  const heading = document.createElement('strong');
  heading.textContent = entity.track_id;
  const context = document.createElement('em');
  context.textContent = `${formatClock(time)}${position?.stale ? ' · son bilinen konum' : ''}`;
  content.append(
    heading,
    context,
    valueRow('Araç', formatVehicleClass(entity.vehicle_class)),
    valueRow('Risk (nihai)', formatRiskLevel(entity.risk_level)),
  );
  if (entity.engine_risk_level !== entity.risk_level) content.append(valueRow('Motor seviyesi', formatRiskLevel(entity.engine_risk_level)));
  if (entity.decision_status !== 'motor') content.append(valueRow('Karar', formatDecisionStatus(entity.decision_status)));
  content.append(
    valueRow('Senaryo', entity.scenario ? formatScenario(entity.scenario) : formatUnavailable()),
    valueRow('Değerlendirme', entity.observed_at ? `${formatSource(entity.source)} · ${entity.observed_at}` : formatUnavailable()),
    valueRow('Üsse mesafe', entity.distance_to_base_m === null ? formatUnavailable() : `${formatMeters(entity.distance_to_base_m)} (${entity.observed_at})`),
  );
  if (reports.length) content.append(valueRow('Rapor olayı', `${reports.length} rapor bu zamana yakın`));
  return content;
}

function untrackedPopup(item: AnalysisVehicle, time: number) {
  const status = untrackedVisibleAt(item, time);
  const content = document.createElement('div');
  content.className = 'analysis-map-popup untracked-popup';
  const heading = document.createElement('strong');
  heading.textContent = item.filtered ? 'ELENEN TESPİT' : 'İZSİZ TESPİT';
  const context = document.createElement('em');
  context.textContent = `${item.vehicle_id} · ${status?.stale ? 'geçmiş gözlem' : 'gözlem zamanı'}`;
  content.append(
    heading,
    context,
    valueRow('Araç', formatVehicleClass(item.label)),
    valueRow('Risk (nihai)', formatRiskLevel(item.risk_level)),
    valueRow('Senaryo', formatScenario(item.scenario)),
    valueRow('Tespit güveni', formatPercent(item.confidence)),
    valueRow('Kare', `${item.frame_id} · ${item.capture_time}`),
    valueRow('Bölge', item.zone),
    valueRow('Üsse mesafe', formatMeters(item.distance_to_base_m)),
  );
  if (item.risk_reasons[0]) content.append(valueRow('Gerekçe', item.risk_reasons[0]));
  return content;
}

function allBounds(analysis: AnalysisData) {
  const bounds = new maplibregl.LngLatBounds([analysis.base.lon, analysis.base.lat], [analysis.base.lon, analysis.base.lat]);
  analysis.zones.forEach(zone => bounds.extend([zone.center[1], zone.center[0]]));
  activeTrackEntities(analysis.entities).forEach(entity => entity.points.forEach(point => bounds.extend([point.lon, point.lat])));
  analysis.untracked.forEach(item => bounds.extend([item.lon, item.lat]));
  return bounds;
}

/** Survives data refreshes so reloading the analysis does not reset the operator's view. */
let savedCamera: { center: [number, number]; zoom: number; bearing: number; pitch: number } | null = null;

function emptyFeatureCollection() {
  return { type: 'FeatureCollection' as const, features: [] };
}

function vehicleLabel(vehicleClass: string) {
  if (vehicleClass === 'truck') return 'KMY';
  if (vehicleClass === 'bus') return 'OTB';
  if (vehicleClass === 'van') return 'VAN';
  if (vehicleClass === 'car') return 'OTO';
  return '?';
}

function mapView(map: LibreMap, mode: '2d' | '3d', duration = 350) {
  map.easeTo({ pitch: mode === '3d' ? 58 : 0, bearing: mode === '3d' ? -28 : 0, duration });
}

type MapInteractionExtensions = LibreMap & {
  setMaxPitch?: (pitch: number) => void;
  touchPitch?: { enable: () => void; disable: () => void };
  touchZoomRotate?: { enable: () => void; enableRotation?: () => void; disableRotation?: () => void };
};

function configureMapInteractions(map: LibreMap, mode: '2d' | '3d') {
  const extended = map as MapInteractionExtensions;
  map.dragPan.enable();
  map.scrollZoom.enable();
  map.doubleClickZoom.enable();
  map.boxZoom.enable();
  map.keyboard.enable();
  extended.touchZoomRotate?.enable();
  extended.setMaxPitch?.(70);
  if (mode === '3d') {
    map.dragRotate.enable();
    extended.touchZoomRotate?.enableRotation?.();
    extended.touchPitch?.enable();
  } else {
    map.dragRotate.disable();
    extended.touchZoomRotate?.disableRotation?.();
    extended.touchPitch?.disable();
  }
}

export function OperationsMap({ analysis, onSelectTrack, visibleTrackIds }: { analysis: AnalysisData; onSelectTrack: (trackId: string) => void; visibleTrackIds?: ReadonlySet<string> }) {
  const container = useRef<HTMLDivElement>(null);
  const shell = useRef<HTMLDivElement>(null);
  const visualControls = useRef<HTMLDivElement>(null);
  const legend = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LibreMap | null>(null);
  const visibleTrackIdsRef = useRef<ReadonlySet<string> | undefined>(visibleTrackIds);
  const selectedTrackId = useTrackingStore(state => state.selectedTrackId);
  const layers = useTrackingStore(state => state.layers);
  const trailMode = usePlaybackStore(state => state.trailMode);
  const [mapError, setMapError] = useState('');
  const [fullscreen, setFullscreen] = useState(false);
  const [viewMode, setViewMode] = useState<'2d' | '3d'>('2d');
  const [legendOpen, setLegendOpen] = useState(false);
  const [visualControlsPosition, setVisualControlsPosition] = useState<{ x: number; y: number } | null>(() => {
    try {
      if (typeof window === 'undefined') return null;
      const stored = localStorage.getItem(visualControlsStorageKey);
      if (!stored) return null;
      const parsed = JSON.parse(stored) as { x?: unknown; y?: unknown };
      return typeof parsed.x === 'number' && typeof parsed.y === 'number' ? { x: parsed.x, y: parsed.y } : null;
    } catch {
      return null;
    }
  });
  const activeEntities = useMemo(() => activeTrackEntities(analysis.entities), [analysis.entities]);

  useEffect(() => { visibleTrackIdsRef.current = visibleTrackIds; }, [visibleTrackIds]);

  useEffect(() => {
    if (!legendOpen) return undefined;
    const closeOnOutside = (event: PointerEvent) => {
      if (!legend.current?.contains(event.target as Node)) setLegendOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setLegendOpen(false);
    };
    document.addEventListener('pointerdown', closeOnOutside);
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.removeEventListener('pointerdown', closeOnOutside);
      document.removeEventListener('keydown', closeOnEscape);
    };
  }, [legendOpen]);

  useEffect(() => {
    if (!visualControlsPosition) return undefined;
    const clampCurrent = () => {
      if (!shell.current || !visualControls.current) return;
      const shellRect = shell.current.getBoundingClientRect();
      const panelRect = visualControls.current.getBoundingClientRect();
      const next = {
        x: Math.min(Math.max(8, visualControlsPosition.x), Math.max(8, shellRect.width - panelRect.width - 8)),
        y: Math.min(Math.max(8, visualControlsPosition.y), Math.max(8, shellRect.height - panelRect.height - 8)),
      };
      if (next.x === visualControlsPosition.x && next.y === visualControlsPosition.y) return;
      setVisualControlsPosition(next);
      try { localStorage.setItem(visualControlsStorageKey, JSON.stringify(next)); } catch { /* Storage may be unavailable. */ }
    };
    clampCurrent();
    window.addEventListener('resize', clampCurrent);
    return () => window.removeEventListener('resize', clampCurrent);
  }, [visualControlsPosition]);

  useEffect(() => {
    if (!container.current) return;
    setMapError('');
    const map = new maplibregl.Map({ container: container.current, style, center: savedCamera?.center ?? [analysis.base.lon, analysis.base.lat], zoom: savedCamera?.zoom ?? 12, bearing: savedCamera?.bearing ?? 0, pitch: savedCamera?.pitch ?? 0, attributionControl: false });
    const restoredCamera = savedCamera !== null;
    mapRef.current = map;
    map.once('style.load', () => applyMapTheme(map));
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right');
    map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-left');
    configureMapInteractions(map, '2d');
    let mapGestureInProgress = false;
    let gestureResetTimer: number | null = null;
    const markGesture = () => {
      if (gestureResetTimer !== null) window.clearTimeout(gestureResetTimer);
      gestureResetTimer = null;
      mapGestureInProgress = true;
    };
    const releaseGesture = () => {
      if (gestureResetTimer !== null) window.clearTimeout(gestureResetTimer);
      gestureResetTimer = window.setTimeout(() => { mapGestureInProgress = false; gestureResetTimer = null; }, 90);
    };
    const gestureEvents = map as unknown as { on: (type: string, listener: () => void) => void; off: (type: string, listener: () => void) => void };
    gestureEvents.on('dragstart', markGesture);
    gestureEvents.on('dragend', releaseGesture);
    gestureEvents.on('rotatestart', markGesture);
    gestureEvents.on('rotateend', releaseGesture);
    gestureEvents.on('pitchstart', markGesture);
    gestureEvents.on('pitchend', releaseGesture);

    const markers: Marker[] = [];
    const trackMarkers = new Map<string, Marker>();
    const untrackedMarkers = new Map<string, Marker>();
    const entities = activeTrackEntities(analysis.entities);
    const byTrackId = new Map(entities.map(entity => [entity.track_id, entity]));
    const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, className: 'vehicle-tooltip', offset: 16 });
    const showPopup = (coordinates: [number, number], content: HTMLElement) => popup.setLngLat(coordinates).setDOMContent(content).addTo(map);
    const hidePopup = () => popup.remove();

    const ensureMapLayers = () => {
      if (!map.getSource('all-track-trails')) {
        map.addSource('all-track-trails', { type: 'geojson', data: emptyFeatureCollection() });
        map.addLayer({ id: 'all-track-trails-casing', type: 'line', source: 'all-track-trails', paint: {
          'line-color': '#061015',
          'line-opacity': ['interpolate', ['linear'], ['zoom'], FAR_MARKER_ZOOM,
            ['case', ['get', 'selected'], 0.68, 0], 13.25, ['case', ['get', 'selected'], 0.68, 0.18]],
          'line-width': ['interpolate', ['linear'], ['zoom'], FAR_MARKER_ZOOM,
            ['case', ['get', 'selected'], 4, 1], 13.25, ['+', ['get', 'width'], 2]],
        } });
        map.addLayer({ id: 'all-track-trails', type: 'line', source: 'all-track-trails', paint: {
          'line-color': ['get', 'color'],
          'line-opacity': ['interpolate', ['linear'], ['zoom'], FAR_MARKER_ZOOM,
            ['case', ['get', 'selected'], 0.98, ['*', ['get', 'opacity'], 0.18]], 13.25, ['get', 'opacity']],
          'line-width': ['interpolate', ['linear'], ['zoom'], FAR_MARKER_ZOOM,
            ['case', ['get', 'selected'], 2.8, 0.65], 13.25, ['get', 'width']],
          'line-dasharray': ['case', ['get', 'selected'], ['literal', [1, 0]], ['literal', [2, 1.2]]],
        } });
      }
      if (!map.getSource('trail-arrows')) {
        map.addSource('trail-arrows', { type: 'geojson', data: emptyFeatureCollection() });
        map.addLayer({ id: 'trail-arrows', type: 'symbol', source: 'trail-arrows', minzoom: FAR_MARKER_ZOOM, layout: { 'text-field': '▲', 'text-size': ['case', ['get', 'selected'], 12, 9], 'text-rotate': ['get', 'heading'], 'text-rotation-alignment': 'map', 'text-allow-overlap': true, 'text-ignore-placement': true }, paint: { 'text-color': ['get', 'color'], 'text-opacity': ['get', 'opacity'], 'text-halo-color': '#071015', 'text-halo-width': 1.2 } });
      }
      if (!map.getSource('selected-track-events')) {
        map.addSource('selected-track-events', { type: 'geojson', data: emptyFeatureCollection() });
        map.addLayer({ id: 'selected-track-events', type: 'circle', source: 'selected-track-events', paint: { 'circle-radius': ['match', ['get', 'type'], 'REPORT', 5, 'STOP', 5, 4], 'circle-color': ['match', ['get', 'type'], 'REPORT', '#d4b35f', 'STOP', '#95a3a8', 'LOITERING', '#d78272', 'CIRCLING', '#c86f7d', '#9ed0bd'], 'circle-opacity': 0.95, 'circle-stroke-color': '#101a20', 'circle-stroke-width': 2 } });
      }
      if (!map.getLayer('operational-3d-buildings') && map.getSource('openmaptiles')) {
        try {
          map.addLayer({ id: 'operational-3d-buildings', type: 'fill-extrusion', source: 'openmaptiles', 'source-layer': 'building', minzoom: 14, filter: ['match', ['geometry-type'], ['MultiPolygon', 'Polygon'], true, false], paint: { 'fill-extrusion-color': '#25333a', 'fill-extrusion-opacity': 0.44, 'fill-extrusion-height': ['case', ['has', 'render_height'], ['get', 'render_height'], ['has', 'height'], ['get', 'height'], 10], 'fill-extrusion-base': ['case', ['has', 'render_min_height'], ['get', 'render_min_height'], 0] }, layout: { visibility: 'none' } });
        } catch (error) {
          console.warn('3D building layer unavailable:', error);
        }
      }
    };

    const updateTrail = () => {
      if (!map.isStyleLoaded()) return;
      ensureMapLayers();
      const selected = useTrackingStore.getState().selectedTrackId;
      const entity = selected ? byTrackId.get(selected) : null;
      const time = usePlaybackStore.getState().currentTime;
      const mode = usePlaybackStore.getState().trailMode;
      const visible = visibleTrackIdsRef.current;
      (map.getSource('all-track-trails') as GeoJSONSource | undefined)?.setData(allTrackTrailFeatures(entities, time, mode, selected, visible));
      (map.getSource('trail-arrows') as GeoJSONSource | undefined)?.setData(trailArrowFeatures(entities, time, mode, selected, visible));
      (map.getSource('selected-track-events') as GeoJSONSource | undefined)?.setData(selectedTrackEventFeatures(entity ?? null, time));
    };

    const updatePlayback = () => {
      const time = usePlaybackStore.getState().currentTime;
      const currentLayers = useTrackingStore.getState().layers;
      const selected = useTrackingStore.getState().selectedTrackId;
      trackMarkers.forEach((marker, trackId) => {
        const entity = byTrackId.get(trackId);
        if (!entity) return;
        const position = positionAtTime(entity, time);
        const element = marker.getElement();
        const passesFilter = !visibleTrackIdsRef.current || visibleTrackIdsRef.current.has(trackId);
        const visible = currentLayers.vehicles && passesFilter && position !== null;
        element.style.display = visible ? '' : 'none';
        element.classList.toggle('selected', trackId === selected);
        element.classList.toggle('context-dimmed', Boolean(selected && trackId !== selected));
        element.classList.toggle('stale', Boolean(position?.stale));
        element.classList.toggle('report-active', reportsAtTime(entity, time).length > 0);
        element.setAttribute('aria-pressed', String(trackId === selected));
        const heading = headingAtTime(entity, time);
        if (heading !== null) element.style.setProperty('--vehicle-heading', `${heading}deg`);
        const sprite = vehicleSprite(entity.vehicle_class, (heading ?? 0) - map.getBearing(), entity.risk_level);
        const image = element.querySelector<HTMLImageElement>('.vehicle-model');
        if (image && sprite && image.getAttribute('src') !== sprite) image.src = sprite;
        if (position) marker.setLngLat([position.lon, position.lat]);
        if (position && trackId === selected && useTrackingStore.getState().followVehicle) map.jumpTo({ center: [position.lon, position.lat] });
      });
      untrackedMarkers.forEach((marker, key) => {
        const item = analysis.untracked[Number(key)];
        const status = item ? untrackedVisibleAt(item, time) : null;
        const element = marker.getElement();
        element.style.display = currentLayers.untracked && status ? '' : 'none';
        element.classList.toggle('stale', Boolean(status?.stale));
        element.classList.toggle('report-active', Boolean(status?.active));
      });
      updateTrail();
    };

    analysis.zones.forEach(zone => {
      const element = document.createElement('button');
      element.type = 'button';
      element.className = 'zone-marker';
      element.setAttribute('aria-label', `Focus map zone ${zone.name}`);
      element.title = `${zone.name} · Zone center`;
      const dot = document.createElement('i');
      const label = document.createElement('span');
      label.textContent = zone.name;
      element.append(dot, label);
      element.addEventListener('click', event => { event.stopPropagation(); map.easeTo({ center: [zone.center[1], zone.center[0]], zoom: 14, duration: 250 }); });
      const marker = new maplibregl.Marker({ element }).setLngLat([zone.center[1], zone.center[0]]).addTo(map);
      markers.push(marker);
    });

    const base = document.createElement('div');
    base.className = 'base-marker';
    base.setAttribute('role', 'img');
    base.setAttribute('aria-label', `Base ${analysis.base.name}`);
    const baseIcon = document.createElement('span');
    baseIcon.textContent = '⌂';
    const baseLabel = document.createElement('strong');
    baseLabel.textContent = analysis.base.name;
    base.append(baseIcon, baseLabel);
    markers.push(new maplibregl.Marker({ element: base }).setLngLat([analysis.base.lon, analysis.base.lat]).addTo(map));

    entities.forEach(entity => {
      const risk = entity.risk_level;
      const button = document.createElement('button');
      button.type = 'button';
      button.className = `analysis-track-marker vehicle-marker risk-${risk.toLowerCase()}`;
      button.dataset.trackId = entity.track_id;
      button.setAttribute('aria-label', `${entity.track_id} ${formatVehicleClass(entity.vehicle_class)} araç detayını aç, genel risk ${formatRiskLevel(risk)}`);
      button.setAttribute('aria-pressed', String(entity.track_id === useTrackingStore.getState().selectedTrackId));
      const glyph = document.createElement('span');
      glyph.className = 'marker-risk-glyph';
      glyph.textContent = riskGlyph[risk];
      const id = document.createElement('span');
      id.className = 'marker-track-id';
      id.textContent = entity.track_id;
      const vehicle = document.createElement('span');
      vehicle.className = `vehicle-silhouette vehicle-${entity.vehicle_class}`;
      vehicle.setAttribute('aria-hidden', 'true');
      const vehicleCab = document.createElement('i');
      const vehicleText = document.createElement('b');
      vehicleText.textContent = vehicleLabel(entity.vehicle_class);
      vehicle.append(vehicleCab, vehicleText);
      const eventDot = document.createElement('i');
      eventDot.className = 'marker-event-dot';
      button.style.setProperty('--track-color', trackColor(entity.track_id));
      appendVehicleModel(button, entity.vehicle_class, risk);
      button.append(glyph, id, vehicle, eventDot);
      const initial = positionAtTime(entity, usePlaybackStore.getState().currentTime) ?? entity.points[0] ?? analysis.base;
      const show = () => {
        const time = usePlaybackStore.getState().currentTime;
        const position = positionAtTime(entity, time);
        if (position) showPopup([position.lon, position.lat], trackPopup(entity, time));
      };
      button.addEventListener('mouseenter', show);
      button.addEventListener('focus', show);
      button.addEventListener('mouseleave', hidePopup);
      button.addEventListener('blur', hidePopup);
      button.addEventListener('click', event => {
        event.stopPropagation();
        if (mapGestureInProgress) return;
        show();
        onSelectTrack(entity.track_id);
      });
      const marker = new maplibregl.Marker({ element: button }).setLngLat([initial.lon, initial.lat]).addTo(map);
      trackMarkers.set(entity.track_id, marker);
      markers.push(marker);
    });

    analysis.untracked.forEach((item, index) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = `untracked-map-marker risk-${item.risk_level.toLowerCase()}${item.filtered ? ' filtered' : ''}`;
      button.dataset.vehicleId = item.vehicle_id;
      button.setAttribute('aria-label', `${item.capture_time} zamanlı izsiz ${formatVehicleClass(item.label)} tespiti, risk ${formatRiskLevel(item.risk_level)}`);
      appendVehicleModel(button, item.label, item.risk_level, 45);
      const glyph = document.createElement('span');
      glyph.className = 'untracked-status-text';
      glyph.textContent = item.risk_level === 'LOW' || item.risk_level === 'UNKNOWN' ? '?' : riskGlyph[item.risk_level];
      const label = document.createElement('span');
      label.className = 'untracked-status-text';
      label.textContent = item.filtered ? 'ELENDİ' : 'İZSİZ';
      button.append(glyph, label);
      const coordinates: [number, number] = [item.lon, item.lat];
      const show = () => showPopup(coordinates, untrackedPopup(item, usePlaybackStore.getState().currentTime));
      button.addEventListener('mouseenter', show);
      button.addEventListener('focus', show);
      button.addEventListener('mouseleave', hidePopup);
      button.addEventListener('blur', hidePopup);
      button.addEventListener('click', event => {
        event.stopPropagation();
        if (mapGestureInProgress) return;
        show();
      });
      const marker = new maplibregl.Marker({ element: button }).setLngLat(coordinates).addTo(map);
      untrackedMarkers.set(String(index), marker);
      markers.push(marker);
    });

    const applyLayers = () => {
      const current = useTrackingStore.getState().layers;
      markers.filter(marker => marker.getElement().classList.contains('zone-marker')).forEach(marker => { marker.getElement().style.display = current.zones ? '' : 'none'; });
      markers.filter(marker => marker.getElement().classList.contains('base-marker')).forEach(marker => { marker.getElement().style.display = current.base ? '' : 'none'; });
      updatePlayback();
    };
    const fitAll = (duration = 0) => map.fitBounds(allBounds(analysis), { padding: 70, maxZoom: 15, duration });
    const focusSelected = () => {
      const selected = useTrackingStore.getState().selectedTrackId;
      const entity = selected ? byTrackId.get(selected) : null;
      const position = entity ? positionAtTime(entity, usePlaybackStore.getState().currentTime) : null;
      if (position) map.easeTo({ center: [position.lon, position.lat], zoom: Math.max(map.getZoom(), 14), duration: 250 });
    };
    const unsubscribeTracking = useTrackingStore.subscribe((state, previous) => {
      if (state.selectedTrackId !== previous.selectedTrackId || state.followVehicle !== previous.followVehicle) { updatePlayback(); updateTrail(); }
      if (state.layers !== previous.layers) applyLayers();
      if (state.viewRequest !== previous.viewRequest) {
        if (state.viewRequest.action === 'vehicle' || state.viewRequest.action === 'route') focusSelected();
        else if (state.viewRequest.action === 'zone') {
          const zone = analysis.zones.find(item => item.name === state.viewRequest.zoneName);
          if (zone) map.easeTo({ center: [zone.center[1], zone.center[0]], zoom: 14, duration: 250 });
        } else if (state.viewRequest.action === 'coordinate' && state.viewRequest.coordinate) {
          map.easeTo({ center: state.viewRequest.coordinate, zoom: Math.max(map.getZoom(), 15), duration: 250 });
        } else {
          if (state.viewRequest.action === 'reset') map.jumpTo({ bearing: 0, pitch: 0 });
          fitAll(250);
        }
      }
    });
    const unsubscribePlayback = usePlaybackStore.subscribe((state, previous) => {
      if (state.currentTime !== previous.currentTime || state.trailMode !== previous.trailMode) updatePlayback();
    });

    const applyZoomDetail = () => {
      const zoom = map.getZoom();
      shell.current?.classList.toggle('vehicle-zoom-mid', zoom >= vehicleMarkerZoom.mid);
      shell.current?.classList.toggle('vehicle-zoom-close', zoom >= vehicleMarkerZoom.label);
      shell.current?.classList.toggle('close-vehicle-zoom', false);
    };
    map.on('zoom', applyZoomDetail);
    const updateVehicleDirections = () => {
      const time = usePlaybackStore.getState().currentTime;
      trackMarkers.forEach((marker, id) => {
        const entity = byTrackId.get(id);
        if (!entity) return;
        const image = marker.getElement().querySelector<HTMLImageElement>('.vehicle-model');
        const src = vehicleSprite(entity.vehicle_class, (headingAtTime(entity, time) ?? 0) - map.getBearing(), entity.risk_level);
        if (image && src && image.getAttribute('src') !== src) image.src = src;
      });
    };
    map.on('rotate', updateVehicleDirections);
    const saveCamera = () => { const center = map.getCenter(); savedCamera = { center: [center.lng, center.lat], zoom: map.getZoom(), bearing: map.getBearing(), pitch: map.getPitch() }; };
    map.on('moveend', saveCamera);
    const themeObserver = new MutationObserver(() => { if (map.getLayer('background')) applyMapTheme(map); });
    themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    map.once('load', () => { ensureMapLayers(); applyMapTheme(map); if (!restoredCamera) fitAll(); updatePlayback(); applyZoomDetail(); });
    map.on('error', event => { console.warn('Map resource error:', event.error.message); setMapError('Harita altlığı yüklenemedi. Analiz işaretleri kullanılmaya devam ediyor.'); });
    const observer = new ResizeObserver(() => map.resize());
    observer.observe(container.current);
    applyLayers();
    return () => {
      unsubscribeTracking();
      unsubscribePlayback();
      map.off('zoom', applyZoomDetail);
      map.off('rotate', updateVehicleDirections);
      map.off('moveend', saveCamera);
      gestureEvents.off('dragstart', markGesture);
      gestureEvents.off('dragend', releaseGesture);
      gestureEvents.off('rotatestart', markGesture);
      gestureEvents.off('rotateend', releaseGesture);
      gestureEvents.off('pitchstart', markGesture);
      gestureEvents.off('pitchend', releaseGesture);
      if (gestureResetTimer !== null) window.clearTimeout(gestureResetTimer);
      observer.disconnect();
      popup.remove();
      markers.forEach(marker => marker.remove());
      themeObserver.disconnect();
      map.remove();
      mapRef.current = null;
    };
  }, [analysis, onSelectTrack]);

  useEffect(() => {
    const time = usePlaybackStore.getState().currentTime;
    shell.current?.querySelectorAll<HTMLElement>('.analysis-track-marker').forEach(marker => {
      const trackId = marker.dataset.trackId;
      const entity = activeEntities.find(item => item.track_id === trackId);
      const temporalPosition = entity ? positionAtTime(entity, time) : null;
      marker.style.display = layers.vehicles && temporalPosition && (!visibleTrackIds || (trackId ? visibleTrackIds.has(trackId) : false)) ? '' : 'none';
    });
    const selected = useTrackingStore.getState().selectedTrackId;
    (mapRef.current?.getSource('all-track-trails') as GeoJSONSource | undefined)?.setData(allTrackTrailFeatures(activeEntities, time, usePlaybackStore.getState().trailMode, selected, visibleTrackIds));
    (mapRef.current?.getSource('trail-arrows') as GeoJSONSource | undefined)?.setData(trailArrowFeatures(activeEntities, time, usePlaybackStore.getState().trailMode, selected, visibleTrackIds));
  }, [activeEntities, layers.vehicles, visibleTrackIds]);

  useEffect(() => {
    const change = () => setFullscreen(document.fullscreenElement === shell.current);
    document.addEventListener('fullscreenchange', change);
    return () => document.removeEventListener('fullscreenchange', change);
  }, []);

  const fitAll = () => mapRef.current?.fitBounds(allBounds(analysis), { padding: 70, maxZoom: 15, duration: 250 });
  const focusSelected = () => {
    const entity = activeEntities.find(item => item.track_id === selectedTrackId);
    const position = entity ? positionAtTime(entity, usePlaybackStore.getState().currentTime) : null;
    if (position) mapRef.current?.easeTo({ center: [position.lon, position.lat], zoom: Math.max(mapRef.current.getZoom(), 14), duration: 250 });
  };
  const setMapMode = (mode: '2d' | '3d') => {
    setViewMode(mode);
    if (!mapRef.current) return;
    configureMapInteractions(mapRef.current, mode);
    mapView(mapRef.current, mode);
    if (mapRef.current.getLayer('operational-3d-buildings')) mapRef.current.setLayoutProperty('operational-3d-buildings', 'visibility', mode === '3d' ? 'visible' : 'none');
  };
  const setTrailMode = (mode: TrailMode) => usePlaybackStore.getState().setTrailMode(mode);
  const toggleFullscreen = async () => { if (!shell.current) return; if (document.fullscreenElement) await document.exitFullscreen(); else await shell.current.requestFullscreen(); };
  const toggle = (layer: 'vehicles' | 'untracked' | 'zones' | 'base') => useTrackingStore.getState().toggleLayer(layer);
  const startVisualControlsDrag = (event: ReactPointerEvent<HTMLButtonElement>) => {
    if (!shell.current || !visualControls.current) return;
    event.preventDefault();
    event.stopPropagation();
    event.currentTarget.setPointerCapture(event.pointerId);
    const shellRect = shell.current.getBoundingClientRect();
    const panelRect = visualControls.current.getBoundingClientRect();
    const startX = event.clientX;
    const startY = event.clientY;
    const initial = visualControlsPosition ?? { x: panelRect.left - shellRect.left, y: panelRect.top - shellRect.top };
    const clamp = (x: number, y: number) => ({
      x: Math.min(Math.max(8, x), Math.max(8, shellRect.width - panelRect.width - 8)),
      y: Math.min(Math.max(8, y), Math.max(8, shellRect.height - panelRect.height - 8)),
    });
    const move = (moveEvent: PointerEvent) => {
      const next = clamp(initial.x + moveEvent.clientX - startX, initial.y + moveEvent.clientY - startY);
      setVisualControlsPosition(next);
      try { localStorage.setItem(visualControlsStorageKey, JSON.stringify(next)); } catch { /* Storage may be unavailable. */ }
    };
    const stop = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', stop);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', stop, { once: true });
  };

  return <div className="map-shell analysis-map-shell" ref={shell}>
    <div ref={container} className="map-canvas" aria-label="Zaman çizelgesi oynatmalı analiz haritası" />
    <div
      className={`map-control-cluster ${visualControlsPosition ? 'dragged' : ''}`}
      ref={visualControls}
      role="toolbar"
      aria-label="Harita kontrol grubu"
      style={visualControlsPosition ? { left: visualControlsPosition.x, top: visualControlsPosition.y, right: 'auto' } : undefined}
    >
      <button className="map-visual-drag-handle" type="button" aria-label="Harita görünüm kontrollerini taşı" onPointerDown={startVisualControlsDrag}>
        <GripVertical size={14} />
      </button>
      <div className="map-toolbar" role="group" aria-label="Harita araçları">
        <Button variant="ghost" onClick={fitAll}><LocateFixed size={15} /><span>Tümünü göster</span></Button>
        <Button variant="ghost" size="icon" aria-label="Seçili track'e odaklan" title="Seçili track'e odaklan" disabled={!selectedTrackId} onClick={focusSelected}><Focus size={16} /></Button>
        <Button variant="ghost" size="icon" aria-label="Harita yönünü sıfırla" title="Harita yönünü sıfırla" onClick={() => { mapRef.current?.jumpTo({ bearing: 0, pitch: 0 }); fitAll(); }}><RotateCcw size={15} /></Button>
        <Button variant="ghost" size="icon" aria-label={fullscreen ? 'Tam ekrandan çık' : 'Tam ekran harita'} title={fullscreen ? 'Tam ekrandan çık' : 'Tam ekran harita'} disabled={!document.fullscreenEnabled} onClick={() => void toggleFullscreen()}>{fullscreen ? <Minimize size={15} /> : <Maximize size={15} />}</Button>
      </div>
      <div className="map-visual-controls" role="group" aria-label="Harita görselleştirme kontrolleri">
        <div className="segmented-control" aria-label="Harita perspektifi">
          <button aria-pressed={viewMode === '2d'} onClick={() => setMapMode('2d')}>2D</button>
          <button aria-pressed={viewMode === '3d'} onClick={() => setMapMode('3d')}><Box size={12} />3D</button>
        </div>
        <div className="segmented-control trail-control" aria-label="Rota izi görünümü">
          <button aria-pressed={trailMode === 'elapsed'} onClick={() => setTrailMode('elapsed')}>Gidilen</button>
          <button aria-pressed={trailMode === 'full'} onClick={() => setTrailMode('full')}>Tüm rota</button>
          <button aria-pressed={trailMode === 'off'} onClick={() => setTrailMode('off')}>Kapalı</button>
        </div>
      </div>
    </div>
    <div className="analysis-map-layers" role="group" aria-label="Harita katmanları">
      <label><input type="checkbox" checked={layers.vehicles} onChange={() => toggle('vehicles')} />Trackler</label>
      <label><input type="checkbox" checked={layers.untracked} onChange={() => toggle('untracked')} />İzsiz</label>
      <label><input type="checkbox" checked={layers.zones} onChange={() => toggle('zones')} />Bölgeler</label>
      <label><input type="checkbox" checked={layers.base} onChange={() => toggle('base')} />Üs</label>
    </div>
    {mapError && <div role="status" className="map-error">{mapError}</div>}
    <div className="map-legend-menu" ref={legend}>
      <button className="map-legend-toggle" type="button" aria-label="Harita legendını aç" aria-expanded={legendOpen} title="Legend" onClick={() => setLegendOpen(open => !open)}><Info size={15} /></button>
      {legendOpen && <div className="map-legend analysis-map-legend" role="dialog" aria-label="Harita legendı">
        <span><i className="legend-base" />Üs</span><span><i className="legend-zone" />Bölge merkezi</span><span><i className="legend-trail" />Rota izi</span><span><i className="legend-event" />Olay</span><span><i className="legend-untracked">?</i>İzsiz tespit</span><span><i className="legend-stale" />Son bilinen</span>{riskLevels.map(level => <span key={level}><i className={`legend-risk risk-${level.toLowerCase()}`}>{riskGlyph[level]}</i>{formatRiskLevel(level)}</span>)}
      </div>}
    </div>
  </div>;
}
