import type { AnalysisData } from '../types/analysis';

export function OperationKpis({ analysis }: { analysis: AnalysisData }) {
  const summary = analysis.operation_summary, risk = summary.risk_counts;
  const cards = [
    ['Takipte', summary.tracked_entity_count, 'neutral'], ['Takipsiz', summary.untracked_observation_count, 'neutral'],
    ['Düşük', risk.LOW, 'low'], ['Orta', risk.MEDIUM, 'medium'], ['Yüksek', risk.HIGH, 'high'], ['Kritik', risk.CRITICAL, 'critical'],
    ['İzlemede', summary.attention_counts.MONITOR, 'neutral'], ['Öncelikli', summary.attention_counts.PRIORITY, 'high'],
    ['Rapor çelişkisi', summary.current_state_counts.report_contradiction, 'high'],
  ] as const;
  return <section className="operation-kpis" aria-label="Operasyon ana göstergeleri">{cards.map(([label, value, tone]) => <div className={`operation-kpi ${tone}`} key={label}><strong>{value}</strong><span>{label}</span></div>)}</section>;
}
