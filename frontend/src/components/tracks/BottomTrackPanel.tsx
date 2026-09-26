import { ChevronDown, ChevronUp, Rows3 } from 'lucide-react';
import type { AnalysisData } from '../../types/analysis';
import { TrackExplorer } from './TrackExplorer';

export function BottomTrackPanel({ analysis, selectedTrackId, onSelectTrack, open, setOpen }: { analysis: AnalysisData; selectedTrackId: string | null; onSelectTrack: (trackId: string) => void; open: boolean; setOpen: (open: boolean) => void }) {
  return <section className={`bottom-track-panel ${open ? 'open' : ''}`} aria-label="İz kayıtları paneli">
    <button className="bottom-panel-toggle" aria-expanded={open} onClick={() => setOpen(!open)}><span><Rows3 size={14} /><strong>Tüm İz Kayıtları</strong><em>{analysis.entities.length}</em></span><small>{open ? 'Listeyi daralt' : 'İzleri ara, filtrele ve incele'}</small>{open ? <ChevronDown size={15} /> : <ChevronUp size={15} />}</button>
    {open && <div className="bottom-panel-content"><TrackExplorer analysis={analysis} selectedTrackId={selectedTrackId} onSelectTrack={onSelectTrack} /></div>}
  </section>;
}
