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
      <Dialog.Title className="sr-only">Çalışma alanı komutları</Dialog.Title><Dialog.Description className="sr-only">Araç ve harita komutlarında ara. Seçmek için ok tuşları ve Enter kullanılır.</Dialog.Description>
      <Command><CommandInput placeholder="Araç veya komut ara…" aria-label="Komutlarda ara" /><CommandList><CommandEmpty>Eşleşen komut veya araç yok.</CommandEmpty>
        <CommandGroup heading="Harita komutları">
          <CommandItem onSelect={() => run(focusVehicleSearch)}>Araç ara <kbd>/</kbd></CommandItem>
          <CommandItem disabled={!tracking.selectedTrackId} onSelect={() => run(() => tracking.requestView('route'))}>Seçili araca odaklan</CommandItem>
          <CommandItem onSelect={() => run(() => tracking.requestView('all'))}>Tüm araçları göster</CommandItem>
          <CommandItem onSelect={() => run(() => tracking.toggleLayer('routes'))}>Rotaları aç/kapat</CommandItem>
          <CommandItem onSelect={() => run(() => tracking.toggleLayer('zones'))}>Bölgeleri aç/kapat</CommandItem>
          <CommandItem disabled={!tracking.selectedTrackId} onSelect={() => run(() => tracking.setFollowVehicle(!tracking.followVehicle))}>Takip modunu aç/kapat <kbd>F</kbd></CommandItem>
          <CommandItem onSelect={() => run(() => tracking.requestView('reset'))}>Görünümü sıfırla</CommandItem>
        </CommandGroup><CommandGroup heading="Araçlar">{tracks.map(track => <CommandItem value={`Araç ${track.id}`} key={track.id} onSelect={() => run(() => { tracking.clearFilters(); tracking.selectTrack(track.id); tracking.requestView('vehicle'); })}>{track.id}<span className="command-meta">Seç ve odaklan</span></CommandItem>)}</CommandGroup>
      </CommandList><div className="command-footer">↑ ↓ Gezin · Enter Seç · Esc Kapat</div></Command>
      <Dialog.Close className="command-close" aria-label="Komutları kapat"><X size={16} /></Dialog.Close>
    </Dialog.Content>
  </Dialog.Portal></Dialog.Root>;
}
