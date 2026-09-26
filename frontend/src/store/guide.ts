import { create } from 'zustand';
import { normalizeGuideSteps, type GuideStep } from '../services/guide';

/** Active highlight sequence. GuideOverlay renders `steps[index]`; clicking the highlighted element calls next(). */
export interface GuideState {
  steps: GuideStep[];
  index: number;
  message: string;
  question: string;
  /** Starts a new sequence (replacing any running one). Returns false when there is nothing to highlight. */
  start: (plan: { steps: unknown; message?: string; question?: string }) => boolean;
  /** Moves to the next step; ends the sequence after the last one. With `from`, only advances if still on that step. */
  next: (from?: number) => void;
  stop: () => void;
}

const idle = { steps: [] as GuideStep[], index: 0, message: '', question: '' };

export const useGuideStore = create<GuideState>((set) => ({
  ...idle,
  start: (plan) => {
    const steps = normalizeGuideSteps(plan.steps);
    set(steps.length ? { steps, index: 0, message: plan.message ?? '', question: plan.question ?? '' } : idle);
    return steps.length > 0;
  },
  next: (from) => set((state) => {
    if (!state.steps.length || (from !== undefined && from !== state.index)) return state;
    return state.index + 1 < state.steps.length ? { index: state.index + 1 } : idle;
  }),
  stop: () => set(idle),
}));
