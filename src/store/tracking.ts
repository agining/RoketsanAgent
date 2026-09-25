import { create } from 'zustand';
import { useWorkspaceStore } from './workspace';
import { defaultFilters, type VehicleFilters } from '../services/vehicle-filters';
export type MapLayer = 'vehicles' | 'routes' | 'zones' | 'base' | 'traveled' | 'future';
export interface TrackingState extends VehicleFilters {
  sidebarOpen: boolean; toggleSidebar: () => void;
  setFilters: (filters: Partial<VehicleFilters>) => void; clearFilters: () => void;
  selectedTrackId: string | null; selectTrack: (id: string | null) => void;
  followVehicle: boolean; setFollowVehicle: (enabled: boolean) => void;
  viewRequest: { action: 'route' | 'reset' | 'all' | 'vehicle' | 'zone'; sequence: number; zoneName?: string }; requestView: (action: 'route' | 'reset' | 'all' | 'vehicle' | 'zone', zoneName?: string) => void;
  layers: Record<MapLayer, boolean>; toggleLayer: (layer: MapLayer) => void;
}
export const useTrackingStore = create<TrackingState>(set => ({
  ...defaultFilters, sidebarOpen: true, toggleSidebar: () => set(state => ({ sidebarOpen: !state.sidebarOpen })),
  setFilters: filters => set(filters), clearFilters: () => set({ ...defaultFilters, activeMovementStates: [] }),
  selectedTrackId: null, selectTrack: selectedTrackId => { if (selectedTrackId) useWorkspaceStore.setState({ inspectorOpen: true }); set(state => ({ selectedTrackId, followVehicle: selectedTrackId ? state.followVehicle : false })); },
  followVehicle: false, setFollowVehicle: enabled => set(state => ({ followVehicle: enabled && !!state.selectedTrackId })),
  viewRequest: { action: 'reset', sequence: 0 }, requestView: (action, zoneName) => set(state => ({ followVehicle: false, viewRequest: { action, zoneName, sequence: state.viewRequest.sequence + 1 } })),
  layers: { vehicles: true, routes: true, zones: true, base: true, traveled: true, future: true },
  toggleLayer: layer => set(state => ({ layers: { ...state.layers, [layer]: !state.layers[layer] } })),
}));
