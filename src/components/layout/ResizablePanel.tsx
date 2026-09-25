import { useRef, useState, type ReactNode } from 'react';
import { useWorkspaceStore } from '../../store/workspace';
export function ResizablePanel({ side, open, children }: { side: 'left' | 'right'; open: boolean; children: ReactNode }) {
  const width = useWorkspaceStore(state => side === 'left' ? state.leftWidth : state.rightWidth);
  const setWidth = useWorkspaceStore(state => state.setWidth);
  const drag = useRef<{ x: number; width: number } | null>(null);
  const [resizing, setResizing] = useState(false);
  return <div className={`resizable-panel ${side} ${open ? 'open' : 'collapsed'} ${resizing ? 'resizing' : ''}`} style={{ width: open ? width : 0 }} inert={!open} aria-hidden={!open}>
    <div className="panel-inner">{children}</div>
    {open && <div className="resize-handle" role="separator" aria-label={`Resize ${side} panel`} aria-orientation="vertical" aria-valuemin={side === 'left' ? 210 : 260} aria-valuemax={side === 'left' ? 330 : 400} aria-valuenow={width} tabIndex={0}
      onPointerDown={event => { if (event.button !== 0) return; event.preventDefault(); drag.current = { x: event.clientX, width }; setResizing(true); event.currentTarget.setPointerCapture(event.pointerId); }}
      onPointerMove={event => { if (drag.current) setWidth(side, drag.current.width + (event.clientX - drag.current.x) * (side === 'left' ? 1 : -1)); }}
      onPointerUp={event => { drag.current = null; setResizing(false); event.currentTarget.releasePointerCapture(event.pointerId); }}
      onLostPointerCapture={() => { drag.current = null; setResizing(false); }}
      onKeyDown={event => { if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return; event.preventDefault(); event.stopPropagation(); setWidth(side, width + (event.key === 'ArrowRight' ? 10 : -10) * (side === 'left' ? 1 : -1)); }} />}
  </div>;
}
