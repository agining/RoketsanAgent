import { formatReportVerdict } from '../../services/formatters';

export function ReportVerdictBadge({ verdict }: { verdict: string }) {
  return <span className={`report-verdict verdict-${verdict}`}>{formatReportVerdict(verdict)}</span>;
}
