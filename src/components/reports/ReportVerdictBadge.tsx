import type { ReportVerdict } from '../../types/analysis';
import { formatReportVerdict } from '../../services/formatters';

export function ReportVerdictBadge({ verdict }: { verdict: ReportVerdict }) {
  return <span className={`report-verdict verdict-${verdict}`}>{formatReportVerdict(verdict)}</span>;
}
