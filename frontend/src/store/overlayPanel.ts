import { create } from 'zustand';
import type { MapOverlayPanel } from '../components/map/MapOverlays';

/**
 * Lets code outside MapOverlays (voice commands) open or close its top-right panels. MapOverlays keeps its own
 * panel state; it applies each new request (sequence bump) and mirrors the open panel back into `current`.
 */
interface OverlayPanelState {
  current: MapOverlayPanel;
  request: { panel: MapOverlayPanel; sequence: number };
  open: (panel: MapOverlayPanel) => void;
  setCurrent: (panel: MapOverlayPanel) => void;
}

export const useOverlayPanelStore = create<OverlayPanelState>(set => ({
  current: null,
  request: { panel: null, sequence: 0 },
  open: panel => set(state => ({ request: { panel, sequence: state.request.sequence + 1 } })),
  setCurrent: current => set({ current }),
}));
