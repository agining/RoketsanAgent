import { useEffect, useState, type CSSProperties } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import { findGuideTarget } from '../../services/guide';
import { useGuideStore } from '../../store/guide';

/** How long a step waits for its element to render (e.g. a panel opened by the previous click) before it is skipped. */
const RESOLVE_TIMEOUT_MS = 1500;
const RING_PADDING = 4;
const TIP_WIDTH = 280;
const TIP_HEIGHT = 130;
const GAP = 12;

type Box = { top: number; left: number; width: number; height: number };

const boxOf = (element: HTMLElement | null): Box | null => {
  const rect = element?.getBoundingClientRect();
  return rect && rect.width > 0 && rect.height > 0 ? { top: rect.top, left: rect.left, width: rect.width, height: rect.height } : null;
};
const sameBox = (a: Box | null, b: Box | null) =>
  a === b || (!!a && !!b && a.top === b.top && a.left === b.left && a.width === b.width && a.height === b.height);
const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(max, value));

/** Places the tooltip below the element, else above, else beside it; always inside the viewport. */
function tipPosition(box: Box | null): CSSProperties {
  const vw = window.innerWidth, vh = window.innerHeight;
  const width = Math.min(TIP_WIDTH, vw - 16);
  if (!box) return { width, left: (vw - width) / 2, bottom: 90 };
  const left = clamp(box.left + box.width / 2 - width / 2, 8, vw - width - 8);
  if (box.top + box.height + GAP + TIP_HEIGHT < vh) return { width, left, top: box.top + box.height + GAP };
  if (box.top - GAP - TIP_HEIGHT > 0) return { width, left, bottom: vh - box.top + GAP };
  const top = clamp(box.top + GAP, 8, vh - TIP_HEIGHT - 8);
  if (box.left + box.width + GAP + width < vw) return { width, top, left: box.left + box.width + GAP };
  if (box.left - GAP - width > 0) return { width, top, left: box.left - GAP - width };
  return { width, top, left };
}

/**
 * Runs the highlight sequence from the guide store: rings the current step's `[data-guide]` element, advances when
 * the user clicks inside it, and ends on the ✕ button (a new question is then needed for another sequence).
 * Opener steps (`opens`) are skipped when the area they open is already visible; steps whose element never
 * appears are skipped after RESOLVE_TIMEOUT_MS.
 */
export function GuideOverlay() {
  const steps = useGuideStore(state => state.steps);
  const index = useGuideStore(state => state.index);
  const message = useGuideStore(state => state.message);
  const step = steps[index] ?? null;
  const [target, setTarget] = useState<HTMLElement | null>(null);
  const [box, setBox] = useState<Box | null>(null);
  // The plan's summary goes on the first step actually shown (earlier opener steps may have been skipped).
  const [messageIndex, setMessageIndex] = useState<number | null>(null);

  useEffect(() => setMessageIndex(null), [steps]);

  useEffect(() => {
    setTarget(null);
    setBox(null);
    if (!step) return;
    const { next } = useGuideStore.getState();
    if (step.opens && findGuideTarget(step.opens)) { next(index); return; }
    const deadline = performance.now() + RESOLVE_TIMEOUT_MS;
    let frame = 0;
    const resolve = () => {
      const element = findGuideTarget(step.id);
      if (element) {
        element.scrollIntoView({ block: 'nearest', inline: 'nearest' });
        setTarget(element);
        setMessageIndex(shown => shown ?? index);
        return;
      }
      if (performance.now() > deadline) { next(index); return; }
      frame = requestAnimationFrame(resolve);
    };
    resolve();
    return () => cancelAnimationFrame(frame);
  }, [step, index]);

  useEffect(() => {
    if (!target || !step) return;
    // The element may re-render (replaced node) or move (panels animate, map resizes): re-query and re-measure each frame.
    const current = () => (target.isConnected ? target : findGuideTarget(step.id));
    let frame = 0;
    const track = () => {
      const next = boxOf(current());
      setBox(previous => (sameBox(previous, next) ? previous : next));
      frame = requestAnimationFrame(track);
    };
    track();
    // Clicks advance; so do value changes (keyboard-operated selects/checkboxes fire no click). Capture phase so the
    // check runs even if the app stops propagation; advance after the event has been handled. `next(index)` makes a
    // click followed by a change on the same step advance only once.
    const onInteract = (event: Event) => {
      const element = current();
      if (element && event.target instanceof Node && element.contains(event.target)) {
        window.setTimeout(() => useGuideStore.getState().next(index), 0);
      }
    };
    document.addEventListener('click', onInteract, true);
    document.addEventListener('change', onInteract, true);
    return () => {
      cancelAnimationFrame(frame);
      document.removeEventListener('click', onInteract, true);
      document.removeEventListener('change', onInteract, true);
    };
  }, [target, step, index]);

  if (!step) return null;
  const last = index + 1 === steps.length;
  return createPortal(<div className="guide-layer">
    {box && <div className="guide-ring" style={{ top: box.top - RING_PADDING, left: box.left - RING_PADDING, width: box.width + RING_PADDING * 2, height: box.height + RING_PADDING * 2 }} />}
    <section className="guide-tip" role="dialog" aria-live="polite" aria-label="Arayüz yardımı" style={tipPosition(box)}>
      <header>
        <span>ADIM {index + 1} / {steps.length}</span>
        <button aria-label="Yardımı kapat" title="Yardımı kapat" onClick={() => useGuideStore.getState().stop()}><X size={13} /></button>
      </header>
      {index === messageIndex && message && <small>{message}</small>}
      <p>{box ? step.instruction : 'Öğe bekleniyor…'}</p>
      <footer>{last ? 'Bitirmek için vurgulanan öğeye tıklayın.' : 'Devam etmek için vurgulanan öğeye tıklayın.'}</footer>
    </section>
  </div>, document.body);
}
