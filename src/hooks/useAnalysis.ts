import { useCallback, useEffect, useState } from 'react';
import { getAnalysis } from '../services/analysisService';
import type { AnalysisData, AnalysisStatus } from '../types/analysis';

export interface UseAnalysisResult { data: AnalysisData | null; status: AnalysisStatus; error: string | null; reload: () => void }
export function useAnalysis(): UseAnalysisResult {
  const [data, setData] = useState<AnalysisData | null>(null);
  const [status, setStatus] = useState<AnalysisStatus>('idle');
  const [error, setError] = useState<string | null>(null);
  const [request, setRequest] = useState(0);
  const reload = useCallback(() => setRequest(value => value + 1), []);
  useEffect(() => {
    const controller = new AbortController(); setStatus('loading'); setError(null);
    getAnalysis(controller.signal).then(result => {
      if (controller.signal.aborted) return;
      setData(result); setStatus(result.entities.length || result.untracked_observations.length ? 'success' : 'empty');
    }).catch(cause => {
      if (controller.signal.aborted) return;
      setStatus('error'); setError(cause instanceof Error ? cause.message : 'Analysis data could not be loaded.');
    });
    return () => controller.abort();
  }, [request]);
  return { data, status, error, reload };
}
