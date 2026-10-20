import { ArrowRight, CircleHelp, TrendingDown, TrendingUp } from 'lucide-react';
import type { MlPredictionInfo } from '../../types';
import { regimeLabel, regimeScore, regimeScoreLabel } from '../../utils/regimeDisplay';

export function RegimeIndicator({ prediction }: { prediction?: MlPredictionInfo }) {
  const available = !!prediction && (prediction.nativeForecast
    ? prediction.nativeForecast.available
    : !prediction.regimeName.startsWith('UNAVAILABLE'));
  const direction = available ? prediction!.signal : null;
  const Icon = direction === 1 ? TrendingUp : direction === -1 ? TrendingDown : direction === 0 ? ArrowRight : CircleHelp;
  const tone = direction === 1 ? 'text-accent-emerald' : direction === -1 ? 'text-accent-rose' : 'text-text-secondary';
  return (
    <div data-regime-direction={direction ?? 'unavailable'} className={`flex items-center gap-2 ${tone}`}>
      <Icon aria-label={direction === 1 ? 'Xu hướng tăng' : direction === -1 ? 'Xu hướng giảm' : direction === 0 ? 'Xu hướng đi ngang' : 'Chưa có dự báo'} className="w-5 h-5 shrink-0" />
      <div>
        <span className="text-sm font-bold block">{regimeLabel(prediction)}</span>
        <span className="text-[11px] block">{regimeScoreLabel(prediction)}: <strong className="font-mono-num">{regimeScore(prediction)}</strong></span>
      </div>
    </div>
  );
}
