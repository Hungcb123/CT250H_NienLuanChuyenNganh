import { useEffect, useSyncExternalStore } from 'react';
import { getVNIndexSummaryApi, VNIndexSummaryData } from './api';

interface IndexState { summary: VNIndexSummaryData | null; error: string | null }
let state: IndexState = { summary: null, error: null };
const listeners = new Set<() => void>();
let pending: Promise<VNIndexSummaryData | null> | null = null;
let generation = 0;

function notify() { listeners.forEach(listener => listener()); }
export function publishVNIndex(summary: VNIndexSummaryData) {
  generation++;
  state = { summary, error: null };
  notify();
}
export function refreshVNIndex(): Promise<VNIndexSummaryData | null> {
  if (pending) return pending;
  const requestGeneration = generation;
  pending = getVNIndexSummaryApi().then(summary => {
    if (requestGeneration !== generation) return state.summary;
    if (summary && Number.isFinite(summary.currentPoints) && summary.currentPoints > 0) {
      publishVNIndex(summary);
    } else {
      state = { summary: state.summary, error: 'Dữ liệu VNINDEX tạm thời chưa cập nhật được. Hệ thống sẽ tự thử lại.' };
      notify();
    }
    return summary;
  }).finally(() => { pending = null; });
  return pending;
}
function subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; }
function snapshot() { return state; }
export function useVNIndex() {
  const current = useSyncExternalStore(subscribe, snapshot);
  useEffect(() => {
    void refreshVNIndex();
    const timer = window.setInterval(() => { void refreshVNIndex(); }, 60_000);
    return () => window.clearInterval(timer);
  }, []);
  return { ...current, refresh: refreshVNIndex };
}
