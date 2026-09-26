import { useEffect, useRef, useState } from 'react';
import { api } from '../services/api';
import { validateGraphAnalysis } from '../services/graphAnalysisService';
import type { GraphAnalysis, GraphWindow } from '../types/graph';

export function useGraphAnalysis(enabled: boolean, sourceRevision: unknown, window: GraphWindow) {
  const [data, setData] = useState<GraphAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [request, setRequest] = useState(0);
  const consumedRequest = useRef(0);
  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    // A previous window must never appear as the result of a newly selected window.
    setData(null);
    const fetch = request !== consumedRequest.current ? api.graphRecompute : api.graphAnalysis;
    consumedRequest.current = request;
    fetch({ start_time: window.start_time, end_time: window.end_time }, controller.signal)
      .then(validateGraphAnalysis)
      .then(result => { if (!controller.signal.aborted) setData(result); })
      .catch(cause => { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : 'Graph analizi alınamadı.'); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [enabled, sourceRevision, window.start_time, window.end_time, request]);
  return { data, loading, error, reload: () => setRequest(value => value + 1) };
}
