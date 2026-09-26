import { useCallback, useEffect, useState } from 'react';
import { getAnalysis } from '../services/analysisService';
import type { AnalysisData, AnalysisStatus } from '../types/analysis';

export interface UseAnalysisResult { data: AnalysisData | null; status: AnalysisStatus; error: string | null; reload: () => void }

/** Loads the analysis from the API. On a failed refresh the last good data stays on screen. */
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
      setData(result); setStatus(result.entities.length || result.untracked.length ? 'success' : 'empty');
    }).catch(cause => {
      if (controller.signal.aborted) return;
      setStatus('error'); setError(cause instanceof Error ? cause.message : 'Analiz verisi alınamadı.');
    });
    return () => controller.abort();
  }, [request]);
  return { data, status, error, reload };
}
