import { create } from 'zustand';
import type { RiskLevel } from '../types/analysis';

export interface ActiveVoiceAlert {
  id: string;
  text: string;
  risk: RiskLevel;
  trackId: string | null;
  vehicleId: string | null;
  frameId: string | null;
  zone: string | null;
  vehicleType: string | null;
  scenario: string | null;
  reason: string | null;
  distanceToBaseM: number | null;
  etaMin: number | null;
  lat: number | null;
  lon: number | null;
  time: string;
}

interface VoiceAlertsState {
  enabled: boolean;
  minRisk: RiskLevel;
  volume: number;
  isSpeaking: boolean;
  activeAlert: ActiveVoiceAlert | null;
  activeAlertText: string | null;
  activeAlertRisk: RiskLevel | null;
  queueCount: number;
  stopRequested: number; // incremented to signal immediate abort
  autoLock: boolean;

  toggleEnabled: () => void;
  setEnabled: (enabled: boolean) => void;
  setMinRisk: (minRisk: RiskLevel) => void;
  setVolume: (volume: number) => void;
  setActiveAlert: (alert: ActiveVoiceAlert | null) => void;
  setSpeaking: (isSpeaking: boolean) => void;
  setQueueCount: (count: number) => void;
  requestStop: () => void;
  toggleAutoLock: () => void;
  setAutoLock: (val: boolean) => void;
}

const STORAGE_KEY = 'atlas_voice_alerts_enabled';
const AUTO_LOCK_KEY = 'atlas_voice_auto_lock';

export const useVoiceAlertsStore = create<VoiceAlertsState>((set) => ({
  enabled: typeof window !== 'undefined' ? localStorage.getItem(STORAGE_KEY) !== 'false' : true,
  minRisk: 'MEDIUM',
  volume: 1.0,
  isSpeaking: false,
  activeAlert: null,
  activeAlertText: null,
  activeAlertRisk: null,
  queueCount: 0,
  stopRequested: 0,
  autoLock: typeof window !== 'undefined' ? localStorage.getItem(AUTO_LOCK_KEY) !== 'false' : true,

  toggleEnabled: () => set((state) => {
    const next = !state.enabled;
    if (typeof window !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, String(next));
    }
    return {
      enabled: next,
      stopRequested: !next ? state.stopRequested + 1 : state.stopRequested,
      activeAlert: !next ? null : state.activeAlert,
      activeAlertText: !next ? null : state.activeAlertText,
      activeAlertRisk: !next ? null : state.activeAlertRisk,
    };
  }),

  setEnabled: (enabled: boolean) => {
    if (typeof window !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, String(enabled));
    }
    set((state) => ({
      enabled,
      stopRequested: !enabled ? state.stopRequested + 1 : state.stopRequested,
      activeAlert: !enabled ? null : state.activeAlert,
      activeAlertText: !enabled ? null : state.activeAlertText,
      activeAlertRisk: !enabled ? null : state.activeAlertRisk,
    }));
  },

  setMinRisk: (minRisk: RiskLevel) => set({ minRisk }),

  setVolume: (volume: number) => set({ volume: Math.max(0, Math.min(1, volume)) }),

  setActiveAlert: (alert) => set({
    activeAlert: alert,
    activeAlertText: alert ? alert.text : null,
    activeAlertRisk: alert ? alert.risk : null,
    isSpeaking: !!alert,
  }),

  setSpeaking: (isSpeaking) => set({ isSpeaking }),

  setQueueCount: (queueCount) => set({ queueCount }),

  requestStop: () => set((state) => ({
    stopRequested: state.stopRequested + 1,
    isSpeaking: false,
    activeAlert: null,
    activeAlertText: null,
    activeAlertRisk: null,
    queueCount: 0,
  })),

  toggleAutoLock: () => set((state) => {
    const next = !state.autoLock;
    if (typeof window !== 'undefined') {
      localStorage.setItem(AUTO_LOCK_KEY, String(next));
    }
    return { autoLock: next };
  }),

  setAutoLock: (autoLock) => {
    if (typeof window !== 'undefined') {
      localStorage.setItem(AUTO_LOCK_KEY, String(autoLock));
    }
    set({ autoLock });
  },
}));
