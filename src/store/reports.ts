import { create } from 'zustand';
import { useWorkspaceStore } from './workspace';

export type ReportMode = 'all' | 'contradictions' | 'supporting' | 'manipulation';
export type ReportSourceFilter = 'all' | 'official' | 'third_party';

interface ReportState {
  selectedReportId: string | null;
  selectReport: (id: string | null) => void;
  mode: ReportMode;
  setMode: (mode: ReportMode) => void;
  source: ReportSourceFilter;
  setSource: (source: ReportSourceFilter) => void;
}

export const useReportStore = create<ReportState>(set => ({
  selectedReportId: null,
  selectReport: selectedReportId => { if (selectedReportId) useWorkspaceStore.setState({ inspectorOpen: true }); set({ selectedReportId }); },
  mode: 'all', setMode: mode => set({ mode }),
  source: 'all', setSource: source => set({ source }),
}));
