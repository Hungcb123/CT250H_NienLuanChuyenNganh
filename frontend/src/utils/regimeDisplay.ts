import type { MlPredictionInfo } from '../types';

export function regimeLabel(prediction?: MlPredictionInfo): string {
  if (!prediction) return 'Chưa có dự báo';
  if (prediction.nativeForecast) {
    if (!prediction.nativeForecast.available) return 'Chưa có dự báo hợp lệ';
    const horizon = prediction.horizonSessions ?? 20;
    return `${prediction.signal === 1 ? 'Nghiêng tăng' : prediction.signal === -1 ? 'Nghiêng giảm' : 'Đi ngang'} · T+${horizon}`;
  }
  return prediction.regimeName.startsWith('UNAVAILABLE') ? 'Chưa có dự báo hợp lệ' : prediction.regimeName;
}

export function regimeScore(prediction?: MlPredictionInfo): string {
  if (!prediction) return 'Chưa có';
  const native = prediction.nativeForecast;
  if (native) {
    if (!native.available || native.netScore == null) return 'Chưa có';
    const magnitude = Math.abs(native.netScore);
    return magnitude > 0 && magnitude < 0.001 ? '<0.001' : magnitude.toFixed(3);
  }
  return prediction.regimeName.startsWith('UNAVAILABLE') ? 'Chưa có' : `${(prediction.confidence * 100).toFixed(0)}%`;
}

export function netScoreLabel(score?: number | null): string {
  if (score == null || !Number.isFinite(score)) return 'Điểm xu hướng';
  return score > 0 ? 'Điểm tăng' : score < 0 ? 'Điểm giảm' : 'Điểm cân bằng';
}

export function regimeScoreLabel(prediction?: MlPredictionInfo): string {
  if (!prediction?.nativeForecast) return 'Độ tin cậy';
  return netScoreLabel(prediction.nativeForecast.available ? prediction.nativeForecast.netScore : null);
}
