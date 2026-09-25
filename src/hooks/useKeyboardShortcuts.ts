import { useEffect } from 'react';
import { usePlaybackStore } from '../store/playback';
import { useTrackingStore } from '../store/tracking';
import { useWorkspaceStore } from '../store/workspace';
import { useAgentStore } from '../store/agent';
import { useReportStore } from '../store/reports';
export function focusVehicleSearch() {
  const tracking = useTrackingStore.getState();
  if (!tracking.sidebarOpen) tracking.toggleSidebar();
  useWorkspaceStore.getState().requestSearch();
}
export function useKeyboardShortcuts() {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.isComposing) return;
      const workspace = useWorkspaceStore.getState();
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); workspace.setCommandOpen(!workspace.commandOpen); return; }
      if (workspace.commandOpen || event.ctrlKey || event.metaKey || event.altKey) return;
      const target = event.target as HTMLElement;
      if (target.closest('input, textarea, select, [contenteditable="true"], [role="combobox"], [role="slider"], [role="separator"], [role="tab"]')) return;
      const playback = usePlaybackStore.getState(), tracking = useTrackingStore.getState();
      if (event.key === ' ' && !target.closest('button, a')) { event.preventDefault(); event.stopPropagation(); if (!event.repeat) playback.togglePlaying(); }
      else if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') { event.preventDefault(); event.stopPropagation(); if (playback.isPlaying) playback.togglePlaying(); playback.seek(playback.currentTime + (event.key === 'ArrowRight' ? 60 : -60)); }
      else if (event.key.toLowerCase() === 'f' && !event.repeat) { event.preventDefault(); tracking.setFollowVehicle(!tracking.followVehicle); }
      else if (event.key === 'Escape') { if (useAgentStore.getState().panel) useAgentStore.getState().setPanel(null); else if (useReportStore.getState().selectedReportId) useReportStore.getState().selectReport(null); else tracking.selectTrack(null); }
      else if (event.key === '/') { event.preventDefault(); focusVehicleSearch(); }
    };
    window.addEventListener('keydown', onKey, true); return () => window.removeEventListener('keydown', onKey, true);
  }, []);
}
