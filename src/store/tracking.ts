import { create } from 'zustand';
import { useWorkspaceStore } from './workspace';
import { defaultFilters, type VehicleFilters } from '../services/vehicle-filters';
import { useReportStore } from './reports';
export type MapLayer = 'vehicles' | 'reports' | 'routes' | 'zones' | 'base' | 'traveled' | 'future';
export type MapMode = 'vehicle' | 'risk' | 'density';
export interface TrackingState extends VehicleFilters {
  sidebarOpen: boolean; toggleSidebar: () => void;
  setFilters: (filters: Partial<VehicleFilters>) => void; clearFilters: () => void;
  selectedTrackId: string | null; selectTrack: (id: string | null) => void;
  followVehicle: boolean; setFollowVehicle: (enabled: boolean) => void;
  viewRequest: { action: 'route' | 'reset' | 'all' | 'vehicle' | 'zone' | 'coordinate'; sequence: number; zoneName?: string; coordinate?: [number, number] }; requestView: (action: 'route' | 'reset' | 'all' | 'vehicle' | 'zone' | 'coordinate', zoneName?: string, coordinate?: [number, number]) => void;
  layers: Record<MapLayer, boolean>; toggleLayer: (layer: MapLayer) => void;
  mapMode: MapMode; setMapMode: (mode: MapMode) => void;
}
export const useTrackingStore = create<TrackingState>(set => ({
  ...defaultFilters, sidebarOpen: true, toggleSidebar: () => set(state => ({ sidebarOpen: !state.sidebarOpen })),
  setFilters: filters => set(filters), clearFilters: () => set({ ...defaultFilters, activeMovementStates: [] }),
  selectedTrackId: null, selectTrack: selectedTrackId => { if (selectedTrackId) { useWorkspaceStore.setState({ inspectorOpen: true }); useReportStore.setState({ selectedReportId: null }); } set(state => ({ selectedTrackId, followVehicle: selectedTrackId ? state.followVehicle : false })); },
  followVehicle: false, setFollowVehicle: enabled => set(state => ({ followVehicle: enabled && !!state.selectedTrackId })),
  viewRequest: { action: 'reset', sequence: 0 }, requestView: (action, zoneName, coordinate) => set(state => ({ followVehicle: false, viewRequest: { action, zoneName, coordinate, sequence: state.viewRequest.sequence + 1 } })),
  layers: { vehicles: true, reports: true, routes: true, zones: true, base: true, traveled: true, future: true },
  toggleLayer: layer => set(state => ({ layers: { ...state.layers, [layer]: !state.layers[layer] } })),
  mapMode: 'vehicle', setMapMode: mapMode => set({ mapMode }),
}));
