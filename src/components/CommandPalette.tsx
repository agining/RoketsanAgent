import * as Dialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import { Command, CommandInput, CommandList, CommandEmpty, CommandGroup, CommandItem } from './ui/command';
import { useWorkspaceStore } from '../store/workspace';
import { useTrackingStore } from '../store/tracking';
import { focusVehicleSearch } from '../hooks/useKeyboardShortcuts';
import type { VehicleTrack } from '../types/tracking';
export function CommandPalette({ tracks }: { tracks: VehicleTrack[] }) {
  const open = useWorkspaceStore(state => state.commandOpen), setOpen = useWorkspaceStore(state => state.setCommandOpen);
  const tracking = useTrackingStore();
  const run = (action: () => void) => { setOpen(false); action(); };
  return <Dialog.Root open={open} onOpenChange={setOpen}><Dialog.Portal container={document.fullscreenElement as HTMLElement | null ?? undefined}>
    <Dialog.Overlay className="command-overlay" /><Dialog.Content className="command-dialog">
      <Dialog.Title className="sr-only">Workspace commands</Dialog.Title><Dialog.Description className="sr-only">Search vehicles and map commands. Use arrow keys and Enter to select.</Dialog.Description>
      <Command><CommandInput placeholder="Search vehicles or commands…" aria-label="Search commands" /><CommandList><CommandEmpty>No matching commands or vehicles.</CommandEmpty>
        <CommandGroup heading="Map commands">
          <CommandItem onSelect={() => run(focusVehicleSearch)}>Search vehicle <kbd>/</kbd></CommandItem>
          <CommandItem disabled={!tracking.selectedTrackId} onSelect={() => run(() => tracking.requestView('route'))}>Focus selected vehicle</CommandItem>
          <CommandItem onSelect={() => run(() => tracking.requestView('all'))}>Fit all tracks</CommandItem>
          <CommandItem onSelect={() => run(() => tracking.toggleLayer('routes'))}>Toggle routes</CommandItem>
          <CommandItem onSelect={() => run(() => tracking.toggleLayer('zones'))}>Toggle zones</CommandItem>
          <CommandItem disabled={!tracking.selectedTrackId} onSelect={() => run(() => tracking.setFollowVehicle(!tracking.followVehicle))}>Toggle follow mode <kbd>F</kbd></CommandItem>
          <CommandItem onSelect={() => run(() => tracking.requestView('reset'))}>Reset view</CommandItem>
        </CommandGroup><CommandGroup heading="Vehicles">{tracks.map(track => <CommandItem value={`Vehicle ${track.id}`} key={track.id} onSelect={() => run(() => { tracking.clearFilters(); tracking.selectTrack(track.id); tracking.requestView('vehicle'); })}>{track.id}<span className="command-meta">Select and focus</span></CommandItem>)}</CommandGroup>
      </CommandList><div className="command-footer">↑ ↓ Navigate · Enter Select · Esc Close</div></Command>
      <Dialog.Close className="command-close" aria-label="Close commands"><X size={16} /></Dialog.Close>
    </Dialog.Content>
  </Dialog.Portal></Dialog.Root>;
}
