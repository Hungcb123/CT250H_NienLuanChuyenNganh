import { useVNIndex } from '../../services/vnindexStore';
import { TechnicalPriceChart } from './TechnicalPriceChart';
interface VNIndexChartProps { height?: number; showControls?: boolean; compact?: boolean }
export function VNIndexChart(props: VNIndexChartProps) {
  const { summary, error } = useVNIndex();
  if (!summary) return <p role="status" className="py-12 text-center text-sm text-text-secondary">{error ?? 'Đang tải VN-Index…'}</p>;
  return <>
    {error && <p role="alert" className="mb-3 text-xs text-accent-rose">{error} Đang hiển thị bản tải thành công gần nhất.</p>}
    <TechnicalPriceChart {...props} bars={summary.history ?? []} name="VN-Index" />
  </>;
}
