import { create } from 'zustand';
interface WorkspaceState {
  inspectorOpen: boolean; toggleInspector: () => void;
  leftWidth: number; rightWidth: number; setWidth: (side: 'left' | 'right', width: number) => void;
  commandOpen: boolean; setCommandOpen: (open: boolean) => void;
  searchRequest: number; requestSearch: () => void;
}
export const useWorkspaceStore = create<WorkspaceState>(set => ({
  inspectorOpen: true, toggleInspector: () => set(state => ({ inspectorOpen: !state.inspectorOpen })),
  leftWidth: 250, rightWidth: 300,
  setWidth: (side, width) => set({ [side === 'left' ? 'leftWidth' : 'rightWidth']: Math.max(side === 'left' ? 210 : 260, Math.min(side === 'left' ? 330 : 400, width)) }),
  commandOpen: false, setCommandOpen: commandOpen => set({ commandOpen }),
  searchRequest: 0, requestSearch: () => set(state => ({ searchRequest: state.searchRequest + 1 })),
}));
