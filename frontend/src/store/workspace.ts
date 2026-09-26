import { create } from 'zustand';
interface WorkspaceState {
  inspectorOpen: boolean; toggleInspector: () => void;
  /** Analyst name sent with "son söz insanda" decisions (shared by the review panel and the detail drawer). */
  analyst: string; setAnalyst: (analyst: string) => void;
}
export const useWorkspaceStore = create<WorkspaceState>(set => ({
  inspectorOpen: false, toggleInspector: () => set(state => ({ inspectorOpen: !state.inspectorOpen })),
  analyst: '', setAnalyst: analyst => set({ analyst }),
}));
