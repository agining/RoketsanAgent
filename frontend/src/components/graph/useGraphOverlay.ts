import { useEffect, type RefObject } from 'react';
import type { GeoJSONSource, Map as LibreMap, MapLayerMouseEvent } from 'maplibre-gl';
import type { FeatureCollection, Point } from 'geojson';
import type { GraphRegion } from '../../types/graph';

export function regionFeatures(regions: GraphRegion[], selected: string | null): FeatureCollection<Point> {
  return { type: 'FeatureCollection', features: regions.map(region => ({
    type: 'Feature', geometry: { type: 'Point', coordinates: [region.location.lon, region.location.lat] },
    properties: { region_id: region.region_id, score: region.interest_score, selected: selected === region.region_id,
      color: region.severity === 'KRITIK' ? '#ec717a' : region.severity === 'YUKSEK' ? '#dfaa68' : region.severity === 'ORTA' ? '#d6c879' : '#70b3a0' },
  })) };
}

export function useGraphOverlay(mapRef: RefObject<LibreMap | null>, regions: GraphRegion[], selected: string | null,
  onSelect: ((regionId: string) => void) | undefined, mapRevision: unknown) {
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const update = () => {
      // The style JSON is ready before remote basemap tiles/sprites finish loading.
      // Waiting for every remote asset would unnecessarily block our local GeoJSON.
      if (!map.getStyle()) return;
      if (!map.getSource('game-graph-regions')) {
        map.addSource('game-graph-regions', { type: 'geojson', data: regionFeatures([], null) });
        map.addLayer({ id: 'game-graph-regions', type: 'circle', source: 'game-graph-regions', paint: {
          'circle-radius': ['+', 8, ['*', ['get', 'score'], 12]], 'circle-color': ['get', 'color'],
          'circle-opacity': 0.28, 'circle-stroke-color': ['get', 'color'],
          'circle-stroke-width': ['case', ['get', 'selected'], 3, 1],
        } });
      }
      (map.getSource('game-graph-regions') as GeoJSONSource).setData(regionFeatures(regions, selected));
    };
    const click = (event: MapLayerMouseEvent) => {
      const id = event.features?.[0]?.properties?.region_id;
      if (typeof id === 'string') onSelect?.(id);
    };
    const enter = () => { map.getCanvas().style.cursor = 'pointer'; };
    const leave = () => { map.getCanvas().style.cursor = ''; };
    map.on('style.load', update);
    map.on('click', 'game-graph-regions', click);
    map.on('mouseenter', 'game-graph-regions', enter);
    map.on('mouseleave', 'game-graph-regions', leave);
    update();
    return () => {
      map.off('style.load', update);
      map.off('click', 'game-graph-regions', click);
      map.off('mouseenter', 'game-graph-regions', enter);
      map.off('mouseleave', 'game-graph-regions', leave);
    };
  }, [mapRef, regions, selected, onSelect, mapRevision]);
}
