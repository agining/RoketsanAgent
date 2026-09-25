import { useEffect, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import type { Map as LibreMap, StyleSpecification } from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import basemapStyle from './basemap-style.json';
import { MapToolbar } from './MapToolbar';
import { filterVehicles, vehicleSnapshot } from '../../services/vehicle-filters';
import type { TrackingData } from '../../types/tracking';
import { futureFeatures, trackingBounds, traveledFeatures } from '../../services/map-data';
import { useTrackingStore } from '../../store/tracking';
import 'maplibre-gl/dist/maplibre-gl.css';
import { usePlaybackStore } from '../../store/playback';
import { getPositionAtTime } from '../../services/playback';

// A local style keeps operational overlays available even if basemap tiles fail.
maplibregl.setWorkerUrl(workerUrl);
const style = basemapStyle as unknown as StyleSpecification;
export function OperationsMap({ data }: { data: TrackingData }) {
  const shell = useRef<HTMLDivElement>(null);
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LibreMap | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!container.current) return;
    let map: LibreMap;
    try {
      map = new maplibregl.Map({ container: container.current, style, center: [data.base.lon, data.base.lat], zoom: 12, attributionControl: { compact: true } });
    } catch { setError('The map could not start. Please enable WebGL in your browser.'); return; }
    mapRef.current = map;
    const markers: maplibregl.Marker[] = [];
    const vehicleButtons = new Map<string, HTMLButtonElement>();
    const vehicleMarkers = new Map<string, maplibregl.Marker>();
    const zoneMarkers: maplibregl.Marker[] = [];
    let baseMarker: maplibregl.Marker | undefined;
    let lastRouteUpdate = -Infinity;
    let lastFilterTime = -Infinity;
    let lastFilterState = useTrackingStore.getState();
    let matching = data.tracks;
    let visibleIds = new Set(data.tracks.map(track => track.id));
    let hoverId: string | null = null;
    const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 18, className: 'vehicle-tooltip' });
    const updateTooltip = () => {
      const track = data.tracks.find(track => track.id === hoverId);
      if (!track || !visibleIds.has(track.id) || !useTrackingStore.getState().layers.vehicles) { hoverId = null; popup.remove(); return; }
      const snapshot = vehicleSnapshot(track, data, usePlaybackStore.getState().currentTime);
      if (!snapshot.position) { hoverId = null; popup.remove(); return; }
      const content = document.createElement('div');
      const title = document.createElement('strong'); title.textContent = track.id;
      const details = document.createElement('span'); details.textContent = `${snapshot.position.speedKmh.toFixed(1)} km/h · ${snapshot.motion} · ${snapshot.baseTrend ?? 'NO BASE TREND'} · ${snapshot.distanceKm!.toFixed(2)} km to base`;
      content.append(title, details); popup.setLngLat([snapshot.position.lon, snapshot.position.lat]).setDOMContent(content).addTo(map);
    };
    const followSelected = () => {
      const { selectedTrackId, followVehicle } = useTrackingStore.getState();
      if (!followVehicle || !selectedTrackId || !visibleIds.has(selectedTrackId) || !useTrackingStore.getState().layers.vehicles) return;
      const track = data.tracks.find(track => track.id === selectedTrackId);
      const position = track && getPositionAtTime(track, usePlaybackStore.getState().currentTime);
      if (position) { map.stop(); map.jumpTo({ center: [position.lon, position.lat] }); }
    };
    const updatePositions = (force = false) => {
      const { currentTime, isPlaying } = usePlaybackStore.getState();
      const state = useTrackingStore.getState(), { layers } = state;
      const filterTime = Math.floor(currentTime * 10) / 10;
      if (force || filterTime !== lastFilterTime || state !== lastFilterState) {
        matching = filterVehicles(data, state, filterTime).map(vehicle => vehicle.track);
        visibleIds = new Set(matching.map(track => track.id));
        lastFilterTime = filterTime; lastFilterState = state;
      }
      data.tracks.forEach(track => {
        const marker = vehicleMarkers.get(track.id); if (!marker) return;
        const position = getPositionAtTime(track, currentTime);
        marker.getElement().style.display = layers.vehicles && position && visibleIds.has(track.id) ? '' : 'none';
        if (!position) return;
        marker.setLngLat([position.lon, position.lat]);
        const arrow = marker.getElement().querySelector<HTMLElement>('.heading-arrow');
        if (arrow) { arrow.style.transform = `rotate(${(position.heading ?? 0) - map.getBearing()}deg)`; arrow.style.visibility = position.heading === null ? 'hidden' : 'visible'; }
      });
      followSelected();
      // Markers follow every frame; GeoJSON worker updates are limited to 20 Hz.
      const now = performance.now();
      if (force || !isPlaying || now - lastRouteUpdate >= 50) {
        const source = map.getSource('traveled') as maplibregl.GeoJSONSource | undefined;
        source?.setData(traveledFeatures(matching, currentTime));
        (map.getSource('routes') as maplibregl.GeoJSONSource | undefined)?.setData(futureFeatures(matching, currentTime));
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
      vehicleButtons.forEach((button, trackId) => {
        button.classList.toggle('selected', id === trackId);
        button.setAttribute('aria-pressed', String(id === trackId));
      });
    };
    const applyLayers = () => {
      const { layers } = useTrackingStore.getState();
      for (const layer of ['routes', 'selected-route', 'traveled-route', 'selected-traveled', 'route-hit-area', 'traveled-hit-area']) {
        const segmentVisible = layer.includes('traveled') ? layers.traveled : layers.future;
        if (map.getLayer(layer)) map.setLayoutProperty(layer, 'visibility', layers.routes && segmentVisible ? 'visible' : 'none');
      }
      zoneMarkers.forEach(marker => { marker.getElement().style.display = layers.zones ? '' : 'none'; });
      if (baseMarker) baseMarker.getElement().style.display = layers.base ? '' : 'none';
      updatePositions(true);
    };
    const unsubscribe = useTrackingStore.subscribe((state, old) => {
      if (state.selectedTrackId !== old.selectedTrackId) applySelection();
      if (state.layers !== old.layers) applyLayers();
      if (state.searchQuery !== old.searchQuery || state.selectedZone !== old.selectedZone || state.activeMovementStates !== old.activeMovementStates || state.minSpeed !== old.minSpeed || state.maxSpeed !== old.maxSpeed) updatePositions(true);
      if (state.followVehicle !== old.followVehicle || state.selectedTrackId !== old.selectedTrackId) followSelected();
      if (state.viewRequest !== old.viewRequest) {
        if (state.viewRequest.action === 'reset' || state.viewRequest.action === 'all') { if (state.viewRequest.action === 'reset') map.jumpTo({ bearing: 0, pitch: 0 }); fit(); }
        else if (state.viewRequest.action === 'zone') {
          const zone = data.zones.find(zone => zone.name === state.viewRequest.zoneName);
          if (zone) map.easeTo({ center: [zone.center[1], zone.center[0]], zoom: 14, duration: focusDuration() });
        }
        else {
          const track = data.tracks.find(track => track.id === state.selectedTrackId);
          const position = track && getPositionAtTime(track, usePlaybackStore.getState().currentTime);
          if (state.viewRequest.action === 'vehicle' && position) map.easeTo({ center: [position.lon, position.lat], zoom: Math.max(map.getZoom(), 14), duration: focusDuration() });
          else if (track?.points.length) {
            const bounds = new maplibregl.LngLatBounds();
            track.points.forEach(point => bounds.extend([point.lon, point.lat]));
            map.fitBounds(bounds, { padding: 65, duration: focusDuration(), maxZoom: 16 });
          }
        }
      }
    });
    const unsubscribePlayback = usePlaybackStore.subscribe((state, old) => {
      if (state.currentTime !== old.currentTime || state.isPlaying !== old.isPlaying) updatePositions();
    });
    map.on('dragstart', () => useTrackingStore.getState().setFollowVehicle(false));
    map.on('rotate', () => updatePositions());
    map.on('style.load', () => {
      map.addSource('routes', { type: 'geojson', data: futureFeatures(matching, usePlaybackStore.getState().currentTime) });
      map.addLayer({ id: 'routes', type: 'line', source: 'routes', layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': '#739da5', 'line-width': 2, 'line-opacity': 0.22 } });
      map.addLayer({ id: 'selected-route', type: 'line', source: 'routes', filter: ['==', ['get', 'trackId'], ''], layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': '#8ee3c0', 'line-width': 3, 'line-opacity': 0.4 } });
      map.addSource('traveled', { type: 'geojson', data: traveledFeatures(data.tracks, usePlaybackStore.getState().currentTime) });
      map.addLayer({ id: 'traveled-route', type: 'line', source: 'traveled', layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': '#83afb5', 'line-width': 2.5, 'line-opacity': 0.9 } });
      map.addLayer({ id: 'selected-traveled', type: 'line', source: 'traveled', filter: ['==', ['get', 'trackId'], ''], layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': '#a2e5c8', 'line-width': 4, 'line-opacity': 1 } });
      // Wider invisible hit area makes routes easier to select.
      map.addLayer({ id: 'route-hit-area', type: 'line', source: 'routes', paint: { 'line-width': 14, 'line-opacity': 0 } });
      map.addLayer({ id: 'traveled-hit-area', type: 'line', source: 'traveled', paint: { 'line-width': 14, 'line-opacity': 0 } });
      for (const hitLayer of ['route-hit-area', 'traveled-hit-area']) {
      map.on('click', hitLayer, event => { const id = event.features?.[0]?.properties?.trackId; if (typeof id === 'string') select(id); });
      map.on('mouseenter', hitLayer, () => { map.getCanvas().style.cursor = 'pointer'; });
      map.on('mouseleave', hitLayer, () => { map.getCanvas().style.cursor = ''; });
      }
      data.zones.forEach(zone => {
        const element = document.createElement('button');
        element.type = 'button'; element.className = 'zone-marker'; element.setAttribute('aria-label', `Focus map zone ${zone.name}`); element.title = `${zone.name} · Zone center`;
        element.addEventListener('click', event => { event.stopPropagation(); useTrackingStore.getState().requestView('zone', zone.name); });
        const dot = document.createElement('i');
        const label = document.createElement('span'); label.textContent = zone.name;
        element.append(dot, label);
        const marker = new maplibregl.Marker({ element }).setLngLat([zone.center[1], zone.center[0]]).addTo(map);
        zoneMarkers.push(marker); markers.push(marker);
      });
      const base = document.createElement('div'); base.className = 'base-marker';
      const baseIcon = document.createElement('span'); baseIcon.textContent = '⌂';
      const baseLabel = document.createElement('strong'); baseLabel.textContent = data.base.name;
      base.append(baseIcon, baseLabel);
      baseMarker = new maplibregl.Marker({ element: base }).setLngLat([data.base.lon, data.base.lat]).addTo(map); markers.push(baseMarker);
      data.tracks.forEach(track => {
        const point = track.points[0]; if (!point) return;
        const button = document.createElement('button');
        button.type = 'button'; button.className = 'vehicle-marker'; button.textContent = track.id;
        const arrow = document.createElement('span'); arrow.className = 'heading-arrow'; arrow.textContent = '▲'; arrow.setAttribute('aria-hidden', 'true'); button.append(arrow);
 button.setAttribute('aria-label', `Select vehicle ${track.id}`);
        const showTooltip = () => { hoverId = track.id; updateTooltip(); };
        const hideTooltip = () => { hoverId = null; popup.remove(); };
        button.addEventListener('mouseenter', showTooltip); button.addEventListener('focus', showTooltip);
        button.addEventListener('mouseleave', hideTooltip); button.addEventListener('blur', hideTooltip);
        button.addEventListener('click', event => { event.stopPropagation(); select(track.id); }); vehicleButtons.set(track.id, button);
        const marker = new maplibregl.Marker({ element: button }).setLngLat([point.lon, point.lat]).addTo(map);
        vehicleMarkers.set(track.id, marker); markers.push(marker);
      });
      applySelection(); applyLayers(); fit(0);
    });
    const observer = new ResizeObserver(() => map.resize()); observer.observe(container.current);
    return () => { unsubscribe(); unsubscribePlayback(); observer.disconnect(); popup.remove(); markers.forEach(marker => marker.remove()); map.remove(); mapRef.current = null; };
  }, [data]);
  return <div className="map-shell" ref={shell}>
    <div ref={container} className="map-canvas" aria-label="Vehicle operations map" />
    <MapToolbar target={shell} />
    {error && <div role="status" className="map-error">{error}</div>}
    <div className="map-legend"><span><i className="legend-route" />Traveled</span><span><i className="legend-route future" />Future</span><span><i className="legend-zone" />Zone center</span><span><i className="legend-base" />Base</span></div>
  </div>;
}
