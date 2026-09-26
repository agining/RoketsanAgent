import { create } from 'zustand';

const storageKey = 'ops-panel-layout-v1';
const sidebarDefault = { x: 10, y: 10, width: 278 };
const detailDefaultWidth = 430;
const agentDefaultWidth = 390;
const helpDefaultWidth = 560;

interface SavedLayout {
  sidebar?: Partial<typeof sidebarDefault>;
  detailWidth?: number;
  agentWidth?: number;
  helpWidth?: number;
}

interface PanelLayoutState {
  sidebar: typeof sidebarDefault;
  detailWidth: number;
  agentWidth: number;
  helpWidth: number;
  setSidebarPosition: (x: number, y: number) => void;
  setSidebarWidth: (width: number) => void;
  setDetailWidth: (width: number) => void;
  setAgentWidth: (width: number) => void;
  setHelpWidth: (width: number) => void;
}

const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);
const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(max, value));

function loadLayout(): SavedLayout {
  if (typeof window === 'undefined') return {};
  try {
    const parsed = JSON.parse(window.localStorage.getItem(storageKey) ?? '{}') as SavedLayout;
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}

function saveLayout(state: Pick<PanelLayoutState, 'sidebar' | 'detailWidth' | 'agentWidth' | 'helpWidth'>) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(storageKey, JSON.stringify({
      sidebar: state.sidebar,
      detailWidth: state.detailWidth,
      agentWidth: state.agentWidth,
      helpWidth: state.helpWidth,
    }));
  } catch {
    // localStorage may be unavailable; the in-memory layout still works.
  }
}

const saved = loadLayout();
const initialSidebar = {
  x: finite(saved.sidebar?.x) ? clamp(saved.sidebar.x, 0, 1200) : sidebarDefault.x,
  y: finite(saved.sidebar?.y) ? clamp(saved.sidebar.y, 0, 900) : sidebarDefault.y,
  width: finite(saved.sidebar?.width) ? clamp(saved.sidebar.width, 230, 420) : sidebarDefault.width,
};

export const usePanelLayoutStore = create<PanelLayoutState>((set, get) => ({
  sidebar: initialSidebar,
  detailWidth: finite(saved.detailWidth) ? clamp(saved.detailWidth, 320, 620) : detailDefaultWidth,
  agentWidth: finite(saved.agentWidth) ? clamp(saved.agentWidth, 320, 560) : agentDefaultWidth,
  helpWidth: finite(saved.helpWidth) ? clamp(saved.helpWidth, 420, 1200) : helpDefaultWidth,
  setSidebarPosition: (x, y) => set(state => {
    const next = { ...state, sidebar: { ...state.sidebar, x, y } };
    saveLayout(next);
    return next;
  }),
  setSidebarWidth: width => set(state => {
    const next = { ...state, sidebar: { ...state.sidebar, width: clamp(width, 230, 420) } };
    saveLayout(next);
    return next;
  }),
  setDetailWidth: width => set(state => {
    const next = { ...state, detailWidth: clamp(width, 320, 620) };
    saveLayout(next);
    return next;
  }),
  setAgentWidth: width => set(state => {
    const next = { ...state, agentWidth: clamp(width, 320, 560) };
    saveLayout(next);
    return next;
  }),
  setHelpWidth: width => set(state => {
    const next = { ...state, helpWidth: clamp(width, 420, 1200) };
    saveLayout(next);
    return next;
  }),
}));
