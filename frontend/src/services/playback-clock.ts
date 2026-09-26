import { usePlaybackStore } from '../store/playback';
/** One frame clock, independent of React renders. Hidden tabs suspend simulation. */
export function startPlaybackClock() {
  let frame = 0, previous: number | null = null;
  const tick = (now: number) => {
    if (previous !== null) usePlaybackStore.getState().advance((now - previous) / 1000);
    previous = now;
    if (usePlaybackStore.getState().isPlaying && !document.hidden) frame = requestAnimationFrame(tick);
  };
  const synchronize = () => {
    cancelAnimationFrame(frame); previous = null;
    if (usePlaybackStore.getState().isPlaying && !document.hidden) frame = requestAnimationFrame(tick);
  };
  const unsubscribe = usePlaybackStore.subscribe((state, old) => { if (state.isPlaying !== old.isPlaying) synchronize(); });
  document.addEventListener('visibilitychange', synchronize); synchronize();
  return () => { cancelAnimationFrame(frame); unsubscribe(); document.removeEventListener('visibilitychange', synchronize); };
}
