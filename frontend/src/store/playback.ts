import { create } from 'zustand';
export const playbackSpeeds = [0.5, 1, 2, 4] as const;
export type PlaybackSpeed = typeof playbackSpeeds[number];
export type TrailMode = 'elapsed' | 'full' | 'off';
const simulationSecondsPerRealSecond = 60;
interface PlaybackState {
  currentTime: number; isPlaying: boolean; playbackSpeed: PlaybackSpeed; minTime: number; maxTime: number;
  trailMode: TrailMode;
  initialize: (min: number, max: number) => void;
  seek: (time: number) => void; togglePlaying: () => void; restart: () => void;
  stepPrevious: () => void; stepNext: () => void; setTrailMode: (mode: TrailMode) => void;
  setSpeed: (speed: PlaybackSpeed) => void; advance: (seconds: number) => void;
}
export const usePlaybackStore = create<PlaybackState>((set) => ({
  currentTime: 0, isPlaying: false, playbackSpeed: 1, minTime: 0, maxTime: 0, trailMode: 'elapsed',
  initialize: (minTime, maxTime) => set(state => {
    const rangeChanged = state.minTime !== minTime || state.maxTime !== maxTime;
    return { minTime, maxTime, currentTime: rangeChanged ? minTime : Math.max(minTime, Math.min(maxTime, state.currentTime)), isPlaying: false };
  }),
  seek: time => set(state => ({ currentTime: Math.max(state.minTime, Math.min(state.maxTime, time)), ...(time >= state.maxTime ? { isPlaying: false } : {}) })),
  togglePlaying: () => set(state => state.maxTime <= state.minTime ? {} : { isPlaying: !state.isPlaying, currentTime: state.currentTime >= state.maxTime ? state.minTime : state.currentTime }),
  restart: () => set(state => ({ currentTime: state.minTime, isPlaying: false })),
  stepPrevious: () => set(state => ({ currentTime: Math.max(state.minTime, state.currentTime - 300), isPlaying: false })),
  stepNext: () => set(state => ({ currentTime: Math.min(state.maxTime, state.currentTime + 300), isPlaying: false })),
  setTrailMode: trailMode => set({ trailMode }),
  setSpeed: playbackSpeed => set({ playbackSpeed }),
  advance: seconds => set(state => {
    if (!state.isPlaying || seconds <= 0) return state;
    const currentTime = Math.min(state.maxTime, state.currentTime + seconds * state.playbackSpeed * simulationSecondsPerRealSecond);
    return { currentTime, isPlaying: currentTime < state.maxTime };
  }),
}));
