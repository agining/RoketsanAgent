import type { ReportVerdict } from '../../types/analysis';

const labels: Record<ReportVerdict, string> = {
  destekler: 'SUPPORTS', celisir: 'CONTRADICTS', kismen_uyumlu: 'PARTIAL',
  dogrulanamaz: 'UNVERIFIED', ilgisiz: 'IRRELEVANT', manipulasyon: 'MANIPULATION',
};

export function ReportVerdictBadge({ verdict }: { verdict: ReportVerdict }) {
  return <span className={`report-verdict verdict-${verdict}`}>{labels[verdict]}</span>;
}
