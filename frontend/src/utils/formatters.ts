// Formatting Utilities for Vietnam Financial & Currency Display

export const formatVND = (amount: number): string => {
  return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(amount);
};

export const formatNumber = (val: number): string => {
  return new Intl.NumberFormat('vi-VN').format(val);
};

export const formatPercent = (val: number, decimals: number = 1): string => {
  return `${(val * 100).toFixed(decimals)}%`;
};
