import { ExternalLink, HelpCircle, X } from 'lucide-react';
import { useState, type PointerEvent as ReactPointerEvent } from 'react';
import { usePanelLayoutStore } from '../../store/panelLayout';

const guideUrl = '/docs/kullanim-kilavuzu.pdf';

export function HelpPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [failed, setFailed] = useState(false);
  const helpWidth = usePanelLayoutStore(state => state.helpWidth);
  const setHelpWidth = usePanelLayoutStore(state => state.setHelpWidth);

  if (!open) return null;

  const openGuide = () => window.open(guideUrl, '_blank', 'noopener,noreferrer');
  const startResize = (event: ReactPointerEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    const startX = event.clientX;
    const startWidth = helpWidth;
    const move = (moveEvent: PointerEvent) => setHelpWidth(startWidth + startX - moveEvent.clientX);
    const stop = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', stop);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', stop, { once: true });
  };

  return (
    <section className="help-drawer" aria-label="Yardım paneli" style={{ width: `min(${helpWidth}px, 85vw, calc(100vw - 22px))` }}>
      <div className="panel-resize-handle left-edge" role="separator" aria-orientation="vertical" aria-label="Yardım paneli genişliği" onPointerDown={startResize} />
      <header>
        <span>
          <HelpCircle size={15} />
          Yardım
        </span>

        <button type="button" aria-label="Yardım panelini kapat" onClick={onClose}>
          <X size={15} />
        </button>
      </header>

      <div className="help-drawer-actions">
        <button type="button" onClick={openGuide}>
          <ExternalLink size={14} />
          Yeni sekmede aç
        </button>
      </div>

      <div className="help-pdf-frame">
        {!failed ? (
          <object
            data={guideUrl}
            type="application/pdf"
            aria-label="Kullanım kılavuzu PDF görüntüleyici"
            onError={() => setFailed(true)}
          >
            <div className="help-pdf-fallback">
              <HelpCircle size={22} />
              <strong>PDF görüntülenemedi</strong>
              <p>Tarayıcı bu PDF'i panel içinde açamadı.</p>
              <button type="button" onClick={openGuide}>
                <ExternalLink size={14} />
                Yeni sekmede aç
              </button>
            </div>
          </object>
        ) : (
          <div className="help-pdf-fallback">
            <HelpCircle size={22} />
            <strong>PDF yüklenemedi</strong>
            <p>Kullanım kılavuzunu yeni sekmede açmayı deneyin.</p>
            <button type="button" onClick={openGuide}>
              <ExternalLink size={14} />
              Yeni sekmede aç
            </button>
          </div>
        )}
      </div>
    </section>
  );
}
