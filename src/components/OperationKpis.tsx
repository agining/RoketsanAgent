import type { AnalysisData } from '../types/analysis';

export function OperationKpis({ analysis }: { analysis: AnalysisData }) {
  const { summary } = analysis, risk = summary.frame_risk_counts;
  const cards = [
    ['Frames', summary.frames, 'neutral'], ['Vehicles', summary.vehicles, 'neutral'],
    ['Low', risk.DUSUK, 'low'], ['Medium', risk.ORTA, 'medium'], ['High', risk.YUKSEK, 'high'], ['Critical', risk.KRITIK, 'critical'],
    ['Recovered', summary.missed_detections_recovered, 'neutral'], ['Off-frame', summary.offframe_tracks, 'neutral'],
    ['Contradictions', summary.report_verdicts.celisir ?? 0, 'high'],
  ] as const;
  return <section className="operation-kpis" aria-label="Operation key performance indicators">{cards.map(([label, value, tone]) => <div className={`operation-kpi ${tone}`} key={label}><strong>{value}</strong><span>{label}</span></div>)}</section>;
}
