import { create } from 'zustand';
export const playbackSpeeds = [1, 5, 15, 60] as const;
export type PlaybackSpeed = typeof playbackSpeeds[number];
interface PlaybackState {
  currentTime: number; isPlaying: boolean; playbackSpeed: PlaybackSpeed; minTime: number; maxTime: number;
  initialize: (min: number, max: number) => void;
  seek: (time: number) => void; togglePlaying: () => void; restart: () => void;
  setSpeed: (speed: PlaybackSpeed) => void; advance: (seconds: number) => void;
}
export const usePlaybackStore = create<PlaybackState>((set) => ({
  currentTime: 0, isPlaying: false, playbackSpeed: 1, minTime: 0, maxTime: 0,
  initialize: (minTime, maxTime) => set({ minTime, maxTime, currentTime: minTime, isPlaying: false }),
  seek: time => set(state => ({ currentTime: Math.max(state.minTime, Math.min(state.maxTime, time)), ...(time >= state.maxTime ? { isPlaying: false } : {}) })),
  togglePlaying: () => set(state => state.maxTime <= state.minTime ? {} : { isPlaying: !state.isPlaying, currentTime: state.currentTime >= state.maxTime ? state.minTime : state.currentTime }),
  restart: () => set(state => ({ currentTime: state.minTime, isPlaying: false })),
  setSpeed: playbackSpeed => set({ playbackSpeed }),
  advance: seconds => set(state => {
    if (!state.isPlaying || seconds <= 0) return state;
    const currentTime = Math.min(state.maxTime, state.currentTime + seconds * state.playbackSpeed);
    return { currentTime, isPlaying: currentTime < state.maxTime };
  }),
}));
