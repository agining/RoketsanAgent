import { create } from 'zustand';

const storageKey = 'ops-timeline-layout-v1';

interface TimelineState {
  compact: boolean;
  setCompact: (compact: boolean) => void;
  toggleCompact: () => void;
}

function loadCompact() {
  if (typeof window === 'undefined') return false;
  try {
    return window.localStorage.getItem(storageKey) === 'compact';
  } catch {
    return false;
  }
}

function saveCompact(compact: boolean) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(storageKey, compact ? 'compact' : 'full');
  } catch {
    // localStorage may be unavailable; the in-memory state still works.
  }
}

export const useTimelineStore = create<TimelineState>((set) => ({
  compact: loadCompact(),
  setCompact: compact => set(() => {
    saveCompact(compact);
    return { compact };
  }),
  toggleCompact: () => set(state => {
    const compact = !state.compact;
    saveCompact(compact);
    return { compact };
  }),
}));
