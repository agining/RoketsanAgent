import { ArrowLeft, ExternalLink, FileText, HelpCircle, PlayCircle, X } from 'lucide-react';
import { useEffect, useState, type PointerEvent as ReactPointerEvent } from 'react';
import { usePanelLayoutStore } from '../../store/panelLayout';

const guideUrl = '/docs/kullanim-kilavuzu.pdf';

export function HelpPanel({ open, onClose, onStartTutorial }: { open: boolean; onClose: () => void; onStartTutorial?: () => void }) {
  const [view, setView] = useState<'menu' | 'pdf'>('menu');
  const [failed, setFailed] = useState(false);
  const helpWidth = usePanelLayoutStore(state => state.helpWidth);
  const setHelpWidth = usePanelLayoutStore(state => state.setHelpWidth);

  useEffect(() => {
    if (open) setView('menu');
  }, [open]);

  if (!open) return null;

  const openGuide = () => window.open(guideUrl, '_blank', 'noopener,noreferrer');
  const showGuide = () => {
    setFailed(false);
    setView('pdf');
  };
  const startTutorial = () => {
    onClose();
    window.setTimeout(() => onStartTutorial?.(), 0);
  };
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

  if (view === 'menu') {
    return (
      <section className="help-menu-popover" aria-label="Yardım menüsü">
        <header>
          <span>
            <HelpCircle size={15} />
            Yardım
          </span>

          <button type="button" aria-label="Yardım menüsünü kapat" onClick={onClose}>
            <X size={15} />
          </button>
        </header>

        <div className="help-choice-grid compact" aria-label="Yardım seçenekleri">
          <button type="button" onClick={showGuide}>
            <FileText size={17} />
            <span>
              <strong>Kullanım Kılavuzu</strong>
              <small>PDF rehberini görüntüle</small>
            </span>
          </button>

          {onStartTutorial && (
            <button type="button" onClick={startTutorial}>
              <PlayCircle size={17} />
              <span>
                <strong>Eğitim Turu</strong>
                <small>Arayüzü adım adım keşfet</small>
              </span>
            </button>
          )}
        </div>
      </section>
    );
  }

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
        <button type="button" onClick={() => setView('menu')}>
          <ArrowLeft size={14} />
          Geri
        </button>

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
