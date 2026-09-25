import { create } from 'zustand';

export type AgentPanel = 'alerts' | 'sitrep' | 'chat' | null;
interface AgentUiState {
  panel: AgentPanel; setPanel: (panel: AgentPanel) => void;
  demoMode: boolean; toggleDemoMode: () => void;
  alertFilter: 'all' | 'critical' | 'contradictions' | 'missed' | 'untracked' | 'manipulation';
  setAlertFilter: (filter: AgentUiState['alertFilter']) => void;
}
export const useAgentStore = create<AgentUiState>(set => ({
  panel: null, setPanel: panel => set({ panel }),
  demoMode: false, toggleDemoMode: () => set(state => ({ demoMode: !state.demoMode, panel: !state.demoMode ? 'alerts' : state.panel })),
  alertFilter: 'all', setAlertFilter: alertFilter => set({ alertFilter, panel: 'alerts' }),
}));
