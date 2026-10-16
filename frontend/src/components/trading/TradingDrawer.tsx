import { useState, useMemo, useEffect } from 'react';
import {
  X, ArrowUpRight, ArrowDownRight, ShieldCheck,
  CheckCircle2, AlertCircle, RefreshCw, Layers
} from 'lucide-react';
import { PortfolioValuation, TradeOrderPayload } from '../../types';
import { VN30_WATCHLIST } from '../../data/vnindexData';
import { formatVND } from '../../utils/formatters';
import { executeTradeOrder, getMarketPrices, MarketPriceItem } from '../../services/api';

interface TradingDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  valuation: PortfolioValuation | null;
  initialTicker?: string;
  initialAction?: 'BUY' | 'SELL';
  onTradeSuccess: () => Promise<void> | void;
}

export function TradingDrawer({
  isOpen,
  onClose,
  valuation,
  initialTicker = 'HPG',
  initialAction = 'BUY',
  onTradeSuccess,
}: TradingDrawerProps) {
  const [ticker, setTicker] = useState<string>(initialTicker);
  const [actionType, setActionType] = useState<'BUY' | 'SELL'>(initialAction);
  const [quantity, setQuantity] = useState<number>(100);
  const [customPrice, setCustomPrice] = useState<number>(0);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [livePrices, setLivePrices] = useState<MarketPriceItem[]>([]);

  // Fetch live prices from DNSE backend
  useEffect(() => {
    getMarketPrices().then(prices => {
      if (prices && prices.length > 0) {
        setLivePrices(prices);
      }
    });
  }, [isOpen]);

  // Sync initial props
  useEffect(() => {
    if (initialTicker) setTicker(initialTicker);
    if (initialAction) setActionType(initialAction);
    setErrorMsg(null);
    setSuccessMsg(null);
  }, [initialTicker, initialAction, isOpen]);

  // Find reference price from live backend prices, VN30 watchlist, or holdings
  const stockMeta = useMemo(() => {
    const fromLive = livePrices.find(
      (p) => p.ticker.toUpperCase() === ticker.toUpperCase()
    );
    if (fromLive && fromLive.price > 0) {
      return {
        name: fromLive.name,
        price: fromLive.price,
        sector: fromLive.assetClass === 'STOCK' ? 'Cổ phiếu' : fromLive.assetClass,
      };
    }

    const fromWatchlist = VN30_WATCHLIST.find(
      (s) => s.ticker.toUpperCase() === ticker.toUpperCase()
    );
    if (fromWatchlist) {
      return {
        name: fromWatchlist.name,
        price: fromWatchlist.price,
        sector: fromWatchlist.sector,
      };
    }

    const fromHoldings = valuation?.holdings.find(
      (h) => h.ticker.toUpperCase() === ticker.toUpperCase()
    );
    if (fromHoldings) {
      return {
        name: fromHoldings.assetName,
        price: fromHoldings.currentPrice,
        sector: fromHoldings.assetClass,
      };
    }

    if (ticker.toUpperCase() === 'GOLD_SJC' || ticker.toUpperCase() === 'GC') {
      return {
        name: 'Vàng miếng SJC 999.9',
        price: 8950000,
        sector: 'Kim loại quý',
      };
    }

    return {
      name: `Cổ phiếu ${ticker.toUpperCase()}`,
      price: 25000,
      sector: 'Niêm yết HOSE',
    };
  }, [ticker, valuation, livePrices]);

  // Set default price when ticker changes
  useEffect(() => {
    setCustomPrice(stockMeta.price);
  }, [stockMeta.price, ticker]);

  // HOSE Ceiling & Floor (+/- 7%)
  const ceilPrice = Math.round((stockMeta.price * 1.07) / 50) * 50;
  const floorPrice = Math.round((stockMeta.price * 0.93) / 50) * 50;

  // Available Cash and Available Asset Holdings
  const availableCash = valuation?.cashBalance ?? 0;
  const holding = valuation?.holdings.find(
    (h) => h.ticker.toUpperCase() === ticker.toUpperCase()
  );
  const availableAssetQty = holding?.quantity ?? 0;

  // Price used for calculation
  const executionPrice = customPrice > 0 ? customPrice : stockMeta.price;
  const grossTotal = quantity * executionPrice;
  const fee = Math.round(grossTotal * 0.001); // 0.1% transaction fee
  const tax = actionType === 'SELL' ? Math.round(grossTotal * 0.001) : 0; // 0.1% personal income tax on sell
  const netTotal = actionType === 'BUY' ? grossTotal + fee : grossTotal - fee - tax;

  // Percentage Quick Allocation
  const handleQuickPercent = (percent: number) => {
    setErrorMsg(null);
    if (actionType === 'BUY') {
      const budget = availableCash * (percent / 100);
      const estLots = Math.floor(budget / (executionPrice * 1.001 * 100)) * 100;
      setQuantity(Math.max(100, estLots));
    } else {
      const shares = Math.floor((availableAssetQty * (percent / 100)) / 100) * 100;
      setQuantity(Math.max(100, shares));
    }
  };

  const handleExecute = async () => {
    setErrorMsg(null);
    setSuccessMsg(null);

    // Validations
    if (quantity <= 0) {
      setErrorMsg('Khối lượng đặt lệnh phải lớn hơn 0');
      return;
    }

    if (quantity % 100 !== 0 && !ticker.includes('GOLD')) {
      setErrorMsg('Theo quy định sàn HOSE, khối lượng khớp lệnh phải là bội số của 100');
      return;
    }

    if (actionType === 'BUY' && netTotal > availableCash) {
      setErrorMsg(
        `Số dư ví VND không đủ để thanh toán. Cần ${formatVND(netTotal)}, hiện có ${formatVND(availableCash)}`
      );
      return;
    }

    if (actionType === 'SELL' && quantity > availableAssetQty) {
      setErrorMsg(
        `Số lượng ${ticker} khả dụng không đủ để bán (${availableAssetQty} CP < ${quantity} CP)`
      );
      return;
    }

    setIsSubmitting(true);
    try {
      const payload: TradeOrderPayload = {
        ticker: ticker.toUpperCase(),
        actionType,
        quantity,
        price: executionPrice,
        notes: `Khớp lệnh ${actionType === 'BUY' ? 'MUA' : 'BÁN'} ${quantity.toLocaleString('vi-VN')} ${ticker} @ ${formatVND(executionPrice)} qua Sàn Paper Trading`,
      };

      await executeTradeOrder(payload);
      setSuccessMsg(
        `Khớp lệnh ${actionType === 'BUY' ? 'MUA' : 'BÁN'} ${quantity.toLocaleString('vi-VN')} ${ticker} thành công! Đã ghi sổ kép ACID.`
      );
      await onTradeSuccess();

      // Reset after success
      setTimeout(() => {
        setSuccessMsg(null);
      }, 4000);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Có lỗi xảy ra khi gửi lệnh';
      setErrorMsg(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden flex justify-end">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs transition-opacity"
        onClick={onClose}
      />

      {/* Slide Drawer Panel */}
      <div className="relative w-full max-w-md bg-surface-container-lowest h-full shadow-2xl flex flex-col z-10 border-l border-border-subtle animate-in slide-in-from-right duration-300">
        {/* Header */}
        <div className="p-5 border-b border-border-subtle flex items-center justify-between bg-surface-container-low">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-surface-container-high text-accent-blue">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-text-primary tracking-tight">
                Sàn Giao Dịch Paper Trading
              </h3>
              <p className="text-xs text-text-secondary">
                Khớp lệnh chuẩn sàn HOSE • Ghi sổ kép ACID
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-text-muted hover:text-text-primary hover:bg-surface-container-high transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {/* Action Type Toggle (BUY vs SELL) */}
          <div className="grid grid-cols-2 gap-2 p-1 rounded-xl bg-surface-container-low border border-border-subtle">
            <button
              onClick={() => {
                setActionType('BUY');
                setErrorMsg(null);
              }}
              className={`py-2.5 px-4 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-2 ${
                actionType === 'BUY'
                  ? 'bg-accent-emerald text-white shadow-sm'
                  : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              <ArrowUpRight className="w-4 h-4" />
              LỆNH MUA
            </button>
            <button
              onClick={() => {
                setActionType('SELL');
                setErrorMsg(null);
              }}
              className={`py-2.5 px-4 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-2 ${
                actionType === 'SELL'
                  ? 'bg-accent-rose text-white shadow-sm'
                  : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              <ArrowDownRight className="w-4 h-4" />
              LỆNH BÁN
            </button>
          </div>

          {/* Asset Selection */}
          <div className="space-y-1.5">
            <label className="text-xs font-bold text-text-primary block">
              Mã Chứng Khoán / Tài Sản
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={ticker}
                onChange={(e) => setTicker(e.target.value.toUpperCase())}
                placeholder="Nhập mã CP (VD: HPG, FPT, LPB, DGC, SJC)"
                className="flex-1 px-3.5 py-2.5 rounded-lg border border-border-subtle bg-surface-container text-sm font-bold uppercase text-text-primary focus:outline-hidden focus:ring-2 focus:ring-accent-blue/30 focus:border-accent-blue"
              />
              <select
                value={ticker}
                onChange={(e) => setTicker(e.target.value)}
                className="px-3 py-2.5 rounded-lg border border-border-subtle bg-surface-container-low text-xs font-medium text-text-primary focus:outline-hidden"
              >
                <optgroup label="VN30 Cập Nhật Mới">
                  {VN30_WATCHLIST.map((s) => (
                    <option key={s.ticker} value={s.ticker}>
                      {s.ticker} ({s.price.toLocaleString('vi-VN')}₫)
                    </option>
                  ))}
                </optgroup>
                <optgroup label="Kim Loại Quý">
                  <option value="GOLD_SJC">GOLD_SJC (Vàng SJC)</option>
                </optgroup>
              </select>
            </div>
            <div className="flex justify-between items-center text-xs text-text-secondary pt-0.5">
              <span>{stockMeta.name}</span>
              <span className="font-semibold text-text-primary">{stockMeta.sector}</span>
            </div>
          </div>

          {/* Reference Price & Bounds */}
          <div className="p-3.5 rounded-xl bg-surface-container-low border border-border-subtle grid grid-cols-3 gap-2 text-center text-xs">
            <div>
              <span className="text-[10px] uppercase font-bold text-accent-rose block">Sàn (-7%)</span>
              <span className="font-mono-num font-bold text-accent-rose">{formatVND(floorPrice)}</span>
            </div>
            <div className="border-x border-border-subtle">
              <span className="text-[10px] uppercase font-bold text-text-muted block">Tham Chiếu</span>
              <span className="font-mono-num font-bold text-text-primary">{formatVND(stockMeta.price)}</span>
            </div>
            <div>
              <span className="text-[10px] uppercase font-bold text-accent-purple block">Trần (+7%)</span>
              <span className="font-mono-num font-bold text-accent-purple">{formatVND(ceilPrice)}</span>
            </div>
          </div>

          {/* Order Price Input */}
          <div className="space-y-1.5">
            <div className="flex justify-between items-center">
              <label className="text-xs font-bold text-text-primary">
                Giá Đặt Lệnh (VND)
              </label>
              <button
                type="button"
                onClick={() => setCustomPrice(stockMeta.price)}
                className="text-[11px] text-accent-blue hover:underline font-medium"
              >
                Giá thị trường (MP)
              </button>
            </div>
            <div className="relative">
              <input
                type="number"
                step="50"
                value={customPrice}
                onChange={(e) => setCustomPrice(Number(e.target.value))}
                className="w-full px-3.5 py-2.5 rounded-lg border border-border-subtle bg-surface-container text-sm font-bold text-text-primary font-mono-num focus:outline-hidden focus:ring-2 focus:ring-accent-blue/30 focus:border-accent-blue"
              />
              <span className="absolute right-3.5 top-2.5 text-xs text-text-muted font-medium">
                VND
              </span>
            </div>
          </div>

          {/* Quantity Input & Stepper */}
          <div className="space-y-1.5">
            <div className="flex justify-between items-center">
              <label className="text-xs font-bold text-text-primary">
                Khối Lượng Khớp Lệnh (Lô 100 CP)
              </label>
              <span className="text-[11px] text-text-secondary">
                {actionType === 'BUY' ? (
                  <>Sức mua: <strong className="text-text-primary font-mono-num">{formatVND(availableCash)}</strong></>
                ) : (
                  <>Khả dụng: <strong className="text-text-primary font-mono-num">{availableAssetQty.toLocaleString()} CP</strong></>
                )}
              </span>
            </div>

            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setQuantity((q) => Math.max(100, q - 100))}
                className="px-3.5 py-2 rounded-lg bg-surface-container-high text-text-primary font-bold hover:bg-surface-container-highest transition-colors"
              >
                -100
              </button>
              <input
                type="number"
                step="100"
                min="100"
                value={quantity}
                onChange={(e) => setQuantity(Number(e.target.value))}
                className="flex-1 px-3.5 py-2 rounded-lg border border-border-subtle bg-surface-container text-sm font-bold text-center text-text-primary font-mono-num focus:outline-hidden focus:ring-2 focus:ring-accent-blue/30 focus:border-accent-blue"
              />
              <button
                type="button"
                onClick={() => setQuantity((q) => q + 100)}
                className="px-3.5 py-2 rounded-lg bg-surface-container-high text-text-primary font-bold hover:bg-surface-container-highest transition-colors"
              >
                +100
              </button>
            </div>

            {/* Quick Percentage Chips */}
            <div className="grid grid-cols-4 gap-1.5 pt-1">
              {[25, 50, 75, 100].map((pct) => (
                <button
                  key={pct}
                  type="button"
                  onClick={() => handleQuickPercent(pct)}
                  className="py-1.5 text-xs font-semibold rounded-md bg-surface-container-low border border-border-subtle hover:bg-surface-container-high text-text-secondary hover:text-text-primary transition-colors"
                >
                  {pct}%
                </button>
              ))}
            </div>
          </div>

          {/* Financial Breakdown Receipt */}
          <div className="p-4 rounded-xl bg-surface-container-low border border-border-subtle space-y-2.5 text-xs">
            <div className="flex justify-between text-text-secondary">
              <span>Giá trị lệnh thô:</span>
              <span className="font-mono-num text-text-primary">{formatVND(grossTotal)}</span>
            </div>
            <div className="flex justify-between text-text-secondary">
              <span>Phí giao dịch (0.1%):</span>
              <span className="font-mono-num text-text-primary">{formatVND(fee)}</span>
            </div>
            {actionType === 'SELL' && (
              <div className="flex justify-between text-text-secondary">
                <span>Thuế chuyển nhượng TNCN (0.1%):</span>
                <span className="font-mono-num text-text-primary">{formatVND(tax)}</span>
              </div>
            )}
            <div className="pt-2 border-t border-border-subtle flex justify-between items-center text-sm font-bold">
              <span className="text-text-primary">
                {actionType === 'BUY' ? 'Tổng thanh toán (Net):' : 'Thực nhận về ví:'}
              </span>
              <span className={`font-mono-num ${actionType === 'BUY' ? 'text-accent-rose' : 'text-accent-emerald'}`}>
                {formatVND(netTotal)}
              </span>
            </div>
            <div className="flex justify-between text-[11px] text-text-muted pt-1">
              <span>Số dư ví VND sau lệnh:</span>
              <span className="font-mono-num font-semibold text-text-secondary">
                {formatVND(actionType === 'BUY' ? availableCash - netTotal : availableCash + netTotal)}
              </span>
            </div>
          </div>

          {/* Error & Success Alerts */}
          {errorMsg && (
            <div className="p-3.5 rounded-lg bg-accent-rose-light border border-accent-rose/30 text-accent-rose text-xs flex items-start gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-accent-rose" />
              <span>{errorMsg}</span>
            </div>
          )}

          {successMsg && (
            <div className="p-3.5 rounded-lg bg-accent-emerald-light border border-accent-emerald/30 text-accent-emerald text-xs flex items-start gap-2">
              <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5 text-accent-emerald" />
              <span>{successMsg}</span>
            </div>
          )}
        </div>

        {/* Footer Execution Action */}
        <div className="p-5 border-t border-border-subtle bg-surface-container-low space-y-2">
          <button
            type="button"
            onClick={handleExecute}
            disabled={isSubmitting}
            className={`w-full py-3.5 rounded-xl text-sm font-bold transition-all shadow-sm flex items-center justify-center gap-2 ${
              actionType === 'BUY'
                ? 'bg-accent-emerald hover:bg-accent-emerald/90 text-white active:scale-98'
                : 'bg-accent-rose hover:bg-accent-rose/90 text-white active:scale-98'
            } ${isSubmitting ? 'opacity-70 cursor-wait' : ''}`}
          >
            {isSubmitting ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin text-white" />
                Đang Khớp Lệnh & Ghi Sổ ACID...
              </>
            ) : (
              <>
                <ShieldCheck className="w-4 h-4 text-white" />
                XÁC NHẬN ĐẶT LỆNH {actionType === 'BUY' ? 'MUA' : 'BÁN'}
              </>
            )}
          </button>
          <p className="text-[11px] text-center text-text-muted">
            Giao dịch mô phỏng hạch toán kép tức thì • Tuân thủ chuẩn kế toán ACID
          </p>
        </div>
      </div>
    </div>
  );
}
