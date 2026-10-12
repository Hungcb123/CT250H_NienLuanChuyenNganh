import { useState, useMemo, useEffect, useCallback } from 'react';
import {
  TrendingUp, TrendingDown, Search, Filter, ShieldAlert,
  Layers, Activity, Plus, ArrowUpRight,
  Sparkles, RefreshCw, CheckCircle2, AlertCircle, Loader2
} from 'lucide-react';
import { VNIndexChart } from '../charts/VNIndexChart';
import {
  VNINDEX_SUMMARY,
  VN30_WATCHLIST,
  VN30StockItem
} from '../../data/vnindexData';
import { formatVND } from '../../utils/formatters';
import { PortfolioValuation } from '../../types';
import { TradingDrawer } from '../trading/TradingDrawer';
import {
  getMarketPrices,
  triggerMarketSync,
  fetchStockQuote,
  registerTrackedStock,
  MarketPriceItem,
  StockLiveQuote
} from '../../services/api';
import { POPULAR_QUICK_STOCKS, getStockMetadata } from '../../data/stockMetadata';

interface MarketTabProps {
  valuation?: PortfolioValuation | null;
  onTradeSuccess?: () => Promise<void> | void;
  onNavigateTab?: (tab: string) => void;
}

export function MarketTab({
  valuation = null,
  onTradeSuccess = () => {},
  onNavigateTab
}: MarketTabProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedSector, setSelectedSector] = useState<string>('ALL');
  const [dbPrices, setDbPrices] = useState<MarketPriceItem[]>([]);
  const [isSyncing, setIsSyncing] = useState<boolean>(false);
  const [syncFeedback, setSyncFeedback] = useState<string | null>(null);

  // Load live prices from database (ingested by DNSE background worker)
  const fetchPrices = useCallback(async () => {
    const prices = await getMarketPrices();
    if (prices && prices.length > 0) {
      setDbPrices(prices);
    }
  }, []);

  useEffect(() => {
    fetchPrices();
  }, [fetchPrices]);

  const handleSyncDnse = async () => {
    setIsSyncing(true);
    setSyncFeedback(null);
    try {
      const res = await triggerMarketSync();
      await fetchPrices();
      setSyncFeedback(`Đã đồng bộ thành công ${res?.totalRecordsUpdated ?? 'mới'} bản ghi từ DNSE OpenAPI KRX!`);
      setTimeout(() => setSyncFeedback(null), 4000);
    } catch (err: any) {
      setSyncFeedback(err.message || 'Lỗi khi đồng bộ DNSE');
      setTimeout(() => setSyncFeedback(null), 4000);
    } finally {
      setIsSyncing(false);
    }
  };

  // Custom User Watchlist saved in LocalStorage
  const [customStocks, setCustomStocks] = useState<VN30StockItem[]>(() => {
    try {
      const saved = localStorage.getItem('equifolio_custom_watchlist');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  // Smart Add Stock State
  const [showAddModal, setShowAddModal] = useState(false);
  const [searchTicker, setSearchTicker] = useState('');
  const [isSearchingQuote, setIsSearchingQuote] = useState(false);
  const [quoteResult, setQuoteResult] = useState<StockLiveQuote | null>(null);
  const [quoteError, setQuoteError] = useState<string | null>(null);
  const [isAddingStock, setIsAddingStock] = useState(false);

  // Trading Drawer state
  const [tradeDrawerOpen, setTradeDrawerOpen] = useState(false);
  const [activeTradeTicker, setActiveTradeTicker] = useState('HPG');
  const [activeTradeAction, setActiveTradeAction] = useState<'BUY' | 'SELL'>('BUY');

  // Combined Watchlist: overlay live prices from DNSE backend
  const combinedWatchlist = useMemo(() => {
    const priceMap = new Map(dbPrices.map(p => [p.ticker.toUpperCase(), p]));
    return [...VN30_WATCHLIST, ...customStocks].map(stock => {
      const live = priceMap.get(stock.ticker.toUpperCase());
      if (live && live.price > 0) {
        const changeRatio = live.changeRatio ?? stock.changePercent;
        return {
          ...stock,
          price: live.price,
          change: live.changeValue ?? stock.change,
          changePercent: changeRatio,
          signal: (changeRatio > 0 ? 'BULLISH' : changeRatio < 0 ? 'BEARISH' : 'NEUTRAL') as 'BULLISH' | 'BEARISH' | 'NEUTRAL'
        };
      }
      return stock;
    });
  }, [customStocks, dbPrices]);

  // Check if ticker is already tracked in watchlist
  const isAlreadyInWatchlist = useMemo(() => {
    const clean = searchTicker.trim().toUpperCase();
    return combinedWatchlist.some(s => s.ticker === clean);
  }, [combinedWatchlist, searchTicker]);

  // Auto-fetch live quote with debounce when searchTicker changes
  useEffect(() => {
    const clean = searchTicker.trim().toUpperCase();
    if (!clean || clean.length < 3) {
      setQuoteResult(null);
      setQuoteError(null);
      setIsSearchingQuote(false);
      return;
    }

    let active = true;
    setIsSearchingQuote(true);
    setQuoteError(null);

    const timer = setTimeout(async () => {
      try {
        const quote = await fetchStockQuote(clean);
        if (!active) return;
        if (quote && quote.price > 0) {
          setQuoteResult(quote);
          setQuoteError(null);
        } else {
          setQuoteResult(null);
          setQuoteError(`Không tìm thấy dữ liệu khớp lệnh sàn cho mã ${clean}`);
        }
      } catch (err: any) {
        if (!active) return;
        setQuoteResult(null);
        setQuoteError(`Lỗi kết nối tra cứu mã ${clean}`);
      } finally {
        if (active) setIsSearchingQuote(false);
      }
    }, 300);

    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [searchTicker]);

  // Save custom stocks when updated
  useEffect(() => {
    localStorage.setItem('equifolio_custom_watchlist', JSON.stringify(customStocks));
  }, [customStocks]);

  // Extract unique sectors
  const sectors = useMemo(() => {
    const s = new Set<string>();
    combinedWatchlist.forEach((item) => s.add(item.sector));
    return ['ALL', ...Array.from(s)];
  }, [combinedWatchlist]);

  // Filter watchlist
  const filteredWatchlist = useMemo(() => {
    return combinedWatchlist.filter((item) => {
      const matchSearch =
        item.ticker.toLowerCase().includes(searchTerm.toLowerCase()) ||
        item.name.toLowerCase().includes(searchTerm.toLowerCase());
      const matchSector = selectedSector === 'ALL' || item.sector === selectedSector;
      return matchSearch && matchSector;
    });
  }, [combinedWatchlist, searchTerm, selectedSector]);

  // Market Breadth Stats
  const breadth = useMemo(() => {
    let advances = 0;
    let declines = 0;
    let unchanged = 0;
    combinedWatchlist.forEach((i) => {
      if (i.changePercent > 0) advances++;
      else if (i.changePercent < 0) declines++;
      else unchanged++;
    });
    return { advances, declines, unchanged };
  }, [combinedWatchlist]);

  // Open trade drawer for a specific stock
  const openTrade = (ticker: string, action: 'BUY' | 'SELL') => {
    setActiveTradeTicker(ticker);
    setActiveTradeAction(action);
    setTradeDrawerOpen(true);
  };

  // Add custom stock with automatic live quote from DNSE
  const handleAddStock = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanTicker = searchTicker.trim().toUpperCase();
    if (!cleanTicker || !quoteResult) return;

    if (isAlreadyInWatchlist) {
      alert(`Mã ${cleanTicker} đã có trong danh sách theo dõi.`);
      return;
    }

    setIsAddingStock(true);
    try {
      const meta = getStockMetadata(cleanTicker);
      // Register in backend database to persist asset and backfill candles
      await registerTrackedStock(cleanTicker, meta.name, meta.sector);

      const newItem: VN30StockItem = {
        ticker: cleanTicker,
        rawTicker: cleanTicker,
        name: meta.name,
        sector: meta.sector,
        price: quoteResult.price,
        change: quoteResult.change,
        changePercent: quoteResult.changePercent,
        volume: quoteResult.volume,
        signal: quoteResult.changePercent > 0 ? 'BULLISH' : quoteResult.changePercent < 0 ? 'BEARISH' : 'NEUTRAL',
      };

      setCustomStocks((prev) => [newItem, ...prev]);
      await fetchPrices(); // refresh live DB prices

      setShowAddModal(false);
      setSearchTicker('');
      setQuoteResult(null);
      setQuoteError(null);
    } catch (err) {
      console.error("Error adding stock", err);
    } finally {
      setIsAddingStock(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* 1. Header Banner */}
      <section className="bg-surface-container-lowest border border-border-subtle rounded-xl p-6 shadow-sm flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold text-text-primary tracking-tight">
              Thị Trường Chứng Khoán & Rổ Chỉ Số VN30
            </h2>
            <span className="px-2.5 py-0.5 rounded-full bg-accent-emerald-light text-accent-emerald text-xs font-semibold border border-accent-emerald/20">
              Rổ Chỉ Số VN30 Chuẩn (30 Mã Cổ Phiếu)
            </span>
            <span className="px-2.5 py-0.5 rounded-full bg-surface-container-high text-text-secondary text-xs font-medium font-mono-num">
              {combinedWatchlist.length} Mã Cổ Phiếu Theo Dõi
            </span>
          </div>
          <p className="text-xs text-text-secondary mt-1">
            Dữ liệu nến ngày & giá khớp lệnh thời gian thực đồng bộ trực tiếp từ DNSE OpenAPI KRX
          </p>
        </div>

        {/* Quick Action Button & Macro Indicator & DNSE Sync */}
        <div className="flex flex-wrap items-center gap-3">
          <button
            onClick={handleSyncDnse}
            disabled={isSyncing}
            className="inline-flex items-center gap-2 px-3.5 py-2.5 rounded-lg bg-surface-container-high hover:bg-surface-container-highest border border-border-subtle text-text-primary text-xs font-bold transition-all shadow-sm active:scale-95 cursor-pointer disabled:opacity-60"
            title="Đồng bộ nến ngày và giá khớp lệnh mới nhất từ DNSE OpenAPI KRX"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-accent-emerald ${isSyncing ? 'animate-spin' : ''}`} />
            <span>{isSyncing ? 'Đang đồng bộ DNSE...' : 'ĐỒNG BỘ DNSE'}</span>
          </button>

          <button
            onClick={() => openTrade('HPG', 'BUY')}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-accent-emerald hover:bg-accent-emerald/90 text-white text-xs font-bold transition-all shadow-sm active:scale-95 cursor-pointer"
          >
            <ArrowUpRight className="w-4 h-4" />
            ĐẶT LỆNH PAPER TRADING
          </button>
          <div className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-surface-container-low border border-border-subtle">
            <ShieldAlert className="w-4 h-4 text-accent-gold" />
            <div className="text-left">
              <p className="text-[10px] uppercase font-bold text-text-muted tracking-wider">Tỷ Lệ Vĩ Mô Vàng / VN-Index</p>
              <p className="text-xs font-bold text-text-primary font-mono-num">
                48.0 <span className="text-accent-emerald font-semibold">(Vùng an toàn)</span>
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Sync feedback notification banner */}
      {syncFeedback && (
        <div className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-accent-emerald-light border border-accent-emerald/30 text-accent-emerald text-xs font-semibold animate-in fade-in">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>{syncFeedback}</span>
        </div>
      )}

      {/* 2. Market Barometer Cards */}
      <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
        {/* Card 1: VN-Index */}
        <div className="bg-surface-container-lowest border border-border-subtle rounded-xl p-5 shadow-sm hover:border-border-highlight transition-all">
          <div className="flex items-center justify-between text-text-muted mb-2">
            <span className="text-xs uppercase tracking-wider font-semibold">Chỉ số VN-Index</span>
            <Activity className="w-5 h-5 text-accent-emerald" />
          </div>
          <div className="text-2xl font-black text-text-primary tracking-tight font-mono-num">
            {VNINDEX_SUMMARY.currentPoints.toLocaleString('vi-VN', { minimumFractionDigits: 2 })}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs">
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-accent-rose-light text-accent-rose font-bold font-mono-num">
              <TrendingDown className="w-3.5 h-3.5" /> {VNINDEX_SUMMARY.changePoints.toFixed(2)} ({VNINDEX_SUMMARY.changePercent.toFixed(2)}%)
            </span>
            <span className="text-text-muted font-mono-num">{(VNINDEX_SUMMARY.latestVolume / 1e6).toFixed(1)}M CP</span>
          </div>
        </div>

        {/* Card 2: Market Breadth */}
        <div className="bg-surface-container-lowest border border-border-subtle rounded-xl p-5 shadow-sm hover:border-border-highlight transition-all">
          <div className="flex items-center justify-between text-text-muted mb-2">
            <span className="text-xs uppercase tracking-wider font-semibold">Độ Rộng Thị Trường (VN30)</span>
            <Layers className="w-5 h-5 text-accent-blue" />
          </div>
          <div className="text-2xl font-black text-text-primary tracking-tight flex items-center gap-3 font-mono-num">
            <span className="text-accent-emerald text-lg font-bold">{breadth.advances} Tăng</span>
            <span className="text-text-muted text-sm font-normal">•</span>
            <span className="text-accent-rose text-lg font-bold">{breadth.declines} Giảm</span>
          </div>
          <div className="mt-3 flex items-center gap-2 text-xs text-text-secondary font-mono-num">
            <span>{breadth.unchanged} Tham chiếu</span>
            <span className="w-1.5 h-1.5 rounded-full bg-border-subtle"></span>
            <span>Khối ngoại: Mua ròng 142 tỷ ₫</span>
          </div>
        </div>

        {/* Card 3: Cash Power */}
        <div className="bg-surface-container-lowest border border-border-subtle rounded-xl p-5 shadow-sm hover:border-border-highlight transition-all">
          <div className="flex items-center justify-between text-text-muted mb-2">
            <span className="text-xs uppercase tracking-wider font-semibold">Sức Mua Khả Dụng (Ví VND)</span>
            <TrendingUp className="w-5 h-5 text-accent-emerald" />
          </div>
          <div className="text-2xl font-black text-accent-emerald tracking-tight font-mono-num">
            {formatVND(valuation?.cashBalance ?? 0)}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-text-secondary">
            <span>Sẵn sàng giải ngân lô 100</span>
            <button
              onClick={() => openTrade('HPG', 'BUY')}
              className="text-accent-blue font-bold hover:underline"
            >
              Mua ngay →
            </button>
          </div>
        </div>

        {/* Card 4: LightGBM Regime Status & Tactical Asset Allocation */}
        <div className="bg-surface-container-lowest border border-border-subtle rounded-xl p-5 shadow-sm hover:border-border-highlight transition-all flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-text-muted mb-2">
              <span className="text-xs uppercase tracking-wider font-semibold">
                Xu Hướng ONNX (Cổ Phiếu VN30)
              </span>
              <span className="p-1 rounded-md bg-accent-purple/10 text-accent-purple">
                <Sparkles className="w-4 h-4" />
              </span>
            </div>

            <div className="flex items-baseline justify-between gap-2">
              <div className="text-base font-bold text-accent-emerald tracking-tight">
                TÍCH LŨY TĂNG TRƯỞNG
              </div>
              <span className="font-mono-num font-bold text-accent-emerald text-xs px-2 py-0.5 rounded-md bg-accent-emerald/10 border border-accent-emerald/20">
                78.4% Tăng
              </span>
            </div>

            <div className="mt-2.5 pt-2 border-t border-border-subtle/50 space-y-1.5 text-[11px]">
              <div className="flex items-center justify-between text-text-secondary">
                <span>• Cổ phiếu VN30 (Risk-On):</span>
                <span className="text-accent-emerald font-semibold">Kỳ vọng T+20 &gt; +5.0%</span>
              </div>
              <div className="flex items-center justify-between text-text-secondary">
                <span>• Vàng SJC (Trú ẩn):</span>
                <span className="text-accent-gold font-semibold">Phòng thủ ổn định (ρ = -0.15)</span>
              </div>
            </div>
          </div>

          <div className="mt-3 pt-2.5 border-t border-border-subtle flex items-center justify-between text-xs">
            <span className="text-[11px] text-text-muted">
              Khuyến nghị TAA: <strong className="text-text-primary">+10% Cổ phiếu</strong>
            </span>
            {onNavigateTab ? (
              <button
                onClick={() => onNavigateTab('markowitz')}
                className="text-accent-blue hover:text-accent-blue/80 font-bold inline-flex items-center gap-1 text-xs cursor-pointer"
              >
                Tái cơ cấu TAA →
              </button>
            ) : (
              <span className="text-accent-emerald font-semibold">Đón sóng chu kỳ</span>
            )}
          </div>
        </div>
      </section>

      {/* 3. Technical Chart (VNIndexChart) */}
      <section className="bg-surface-container-lowest border border-border-subtle rounded-xl p-6 shadow-sm">
        <VNIndexChart />
      </section>

      {/* 4. Watchlist & Trading Table */}
      <section className="bg-surface-container-lowest border border-border-subtle rounded-xl p-6 shadow-sm space-y-4">
        {/* Table Controls */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-border-subtle pb-4">
          <div>
            <h3 className="text-base font-bold text-text-primary tracking-tight">
              Bảng Giá Trực Tuyến & Đặt Lệnh Khớp Tức Thì
            </h3>
            <p className="text-xs text-text-secondary">
              Bấm vào nút <strong className="text-accent-emerald">MUA</strong> hoặc <strong className="text-accent-rose">BÁN</strong> trên từng mã để mở bảng đặt lệnh Paper Trading
            </p>
          </div>

          <div className="flex items-center gap-2">
            {/* Search Input */}
            <div className="relative">
              <Search className="w-4 h-4 text-text-muted absolute left-3 top-2.5" />
              <input
                type="text"
                placeholder="Tìm mã hoặc tên..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-9 pr-3 py-2 text-xs rounded-lg border border-border-subtle bg-surface-container-low text-text-primary focus:outline-hidden focus:border-accent-emerald w-56"
              />
            </div>

            {/* Add Custom Stock Button */}
            <button
              onClick={() => setShowAddModal(true)}
              className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-bold rounded-lg bg-surface-container-high hover:bg-surface-container-highest text-text-primary border border-border-subtle transition-colors shrink-0"
            >
              <Plus className="w-3.5 h-3.5" />
              Thêm Mã Tự Do
            </button>
          </div>
        </div>

        {/* Sector Filter Chips */}
        <div className="flex flex-wrap items-center gap-1.5 pb-2 text-xs">
          <span className="text-[11px] font-semibold text-text-muted mr-1 flex items-center gap-1">
            <Filter className="w-3 h-3" /> Nhóm ngành:
          </span>
          {sectors.map((sec) => (
            <button
              key={sec}
              type="button"
              onClick={() => setSelectedSector(sec)}
              className={`px-3 py-1 rounded-full text-xs font-semibold transition-all ${
                selectedSector === sec
                  ? 'bg-accent-emerald text-white shadow-xs'
                  : 'bg-surface-container-low text-text-secondary hover:text-text-primary hover:bg-surface-container-high'
              }`}
            >
              {sec === 'ALL' ? 'Tất cả' : sec}
            </button>
          ))}
        </div>

        {/* Stock Quotes Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-border-subtle text-text-muted uppercase text-[11px]">
                <th className="pb-3 font-semibold">Mã CP</th>
                <th className="pb-3 font-semibold">Tên Doanh Nghiệp</th>
                <th className="pb-3 font-semibold">Nhóm Ngành</th>
                <th className="pb-3 font-semibold text-right">Giá Khớp</th>
                <th className="pb-3 font-semibold text-right">Biến Động 1D</th>
                <th className="pb-3 font-semibold text-right">Khối Lượng</th>
                <th className="pb-3 font-semibold text-center">Tín Hiệu ONNX</th>
                <th className="pb-3 font-semibold text-right">Đặt Lệnh</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle">
              {filteredWatchlist.map((item) => {
                const isPos = item.changePercent > 0;
                const isNeg = item.changePercent < 0;
                return (
                  <tr key={item.rawTicker} className="hover:bg-surface-container-low transition-colors">
                    <td className="py-3 font-bold text-text-primary">
                      <span className="px-2 py-0.5 rounded bg-surface-container-high font-mono-num text-xs font-bold text-text-primary">
                        {item.ticker}
                      </span>
                    </td>
                    <td className="py-3 text-text-primary font-medium">{item.name}</td>
                    <td className="py-3 text-text-secondary">
                      <span className="px-2 py-0.5 rounded bg-surface-container-low text-[11px] font-medium border border-border-subtle">
                        {item.sector}
                      </span>
                    </td>
                    <td className="py-3 text-right font-mono-num font-bold text-text-primary">
                      {item.rawTicker.includes('GC=F')
                        ? `$${item.price.toFixed(2)}`
                        : formatVND(item.price)}
                    </td>
                    <td className="py-3 text-right font-mono-num font-bold">
                      <span className={`inline-flex items-center gap-0.5 ${
                        isPos ? 'text-accent-emerald' : isNeg ? 'text-accent-rose' : 'text-text-muted'
                      }`}>
                        {isPos ? <TrendingUp className="w-3.5 h-3.5" /> : isNeg ? <TrendingDown className="w-3.5 h-3.5" /> : null}
                        {item.changePercent > 0 ? '+' : ''}{item.changePercent.toFixed(2)}%
                      </span>
                    </td>
                    <td className="py-3 text-right font-mono-num text-text-secondary">
                      {item.volume.toLocaleString('vi-VN')}
                    </td>
                    <td className="py-3 text-center">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                        item.signal === 'BULLISH'
                          ? 'bg-accent-emerald-light text-accent-emerald border border-accent-emerald/20'
                          : item.signal === 'BEARISH'
                          ? 'bg-accent-rose-light text-accent-rose border border-accent-rose/20'
                          : 'bg-surface-container-high text-text-secondary'
                      }`}>
                        {item.signal === 'BULLISH' ? '+1 Mua' : item.signal === 'BEARISH' ? '-1 Bán' : '0 Trung lập'}
                      </span>
                    </td>
                    {/* Action Buttons */}
                    <td className="py-3 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => openTrade(item.ticker, 'BUY')}
                          className="px-2.5 py-1 rounded-md bg-accent-emerald-light text-accent-emerald hover:bg-accent-emerald hover:text-white font-bold text-[11px] transition-all"
                        >
                          MUA
                        </button>
                        <button
                          onClick={() => openTrade(item.ticker, 'SELL')}
                          className="px-2.5 py-1 rounded-md bg-accent-rose-light text-accent-rose hover:bg-accent-rose hover:text-white font-bold text-[11px] transition-all"
                        >
                          BÁN
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* Modal: Smart Add Stock with Live Market Quote */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div
            className="fixed inset-0 bg-slate-950/70 backdrop-blur-sm"
            onClick={() => {
              setShowAddModal(false);
              setSearchTicker('');
              setQuoteResult(null);
              setQuoteError(null);
            }}
          />
          <div className="relative bg-surface-container-lowest rounded-2xl shadow-2xl max-w-md w-full p-6 space-y-5 border border-border-subtle z-10 animate-in fade-in zoom-in-95 duration-150">
            {/* Header */}
            <div className="flex items-start justify-between">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <div className="p-1.5 rounded-lg bg-accent-blue/10 text-accent-blue">
                    <Sparkles className="w-4 h-4" />
                  </div>
                  <h3 className="text-base font-bold text-text-primary tracking-tight">
                    Thêm Cổ Phiếu Theo Dõi
                  </h3>
                </div>
                <p className="text-xs text-text-secondary leading-relaxed">
                  Nhập mã CP để tự động lấy tên công ty, ngành và giá khớp lệnh trực tiếp từ sàn qua DNSE OpenAPI.
                </p>
              </div>
            </div>

            <form onSubmit={handleAddStock} className="space-y-4">
              {/* Quick Pick Chips */}
              <div>
                <label className="text-[11px] font-bold text-text-muted uppercase tracking-wider block mb-1.5">
                  Gợi ý mã giao dịch sôi động
                </label>
                <div className="flex flex-wrap gap-1.5">
                  {POPULAR_QUICK_STOCKS.map((sym) => {
                    const isSelected = searchTicker === sym;
                    const isTracked = combinedWatchlist.some((s) => s.ticker === sym);
                    return (
                      <button
                        type="button"
                        key={sym}
                        onClick={() => setSearchTicker(sym)}
                        className={`px-2.5 py-1 rounded-md text-xs font-bold transition-all cursor-pointer ${
                          isSelected
                            ? 'bg-accent-blue text-white shadow-xs'
                            : isTracked
                            ? 'bg-surface-container-high text-text-muted border border-border-subtle opacity-70'
                            : 'bg-surface-container hover:bg-surface-container-high text-text-primary border border-border-subtle hover:border-accent-blue/30'
                        }`}
                      >
                        {sym}
                        {isTracked && <span className="ml-1 text-[10px] text-accent-emerald">✓</span>}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Ticker Input with Live Indicator */}
              <div>
                <label className="font-bold text-xs text-text-primary block mb-1.5">
                  Mã Cổ Phiếu (HOSE / HNX)
                </label>
                <div className="relative">
                  <Search className="w-4 h-4 text-text-muted absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    required
                    value={searchTicker}
                    onChange={(e) => setSearchTicker(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ''))}
                    placeholder="VD: VIX, DIG, NVL, DGC, PVD..."
                    maxLength={10}
                    className="w-full pl-9 pr-10 py-2.5 rounded-xl border border-border-subtle bg-surface-container uppercase font-bold text-text-primary tracking-wider text-sm focus:border-accent-blue focus:ring-1 focus:ring-accent-blue outline-none transition-all"
                  />
                  {isSearchingQuote && (
                    <Loader2 className="w-4 h-4 text-accent-blue animate-spin absolute right-3 top-1/2 -translate-y-1/2" />
                  )}
                </div>
              </div>

              {/* Live Quote Result Card */}
              {isSearchingQuote && (
                <div className="p-4 rounded-xl border border-border-subtle bg-surface-container/60 flex items-center justify-center gap-2.5 text-xs text-text-secondary animate-pulse">
                  <Loader2 className="w-4 h-4 text-accent-blue animate-spin" />
                  <span>Đang truy vấn bảng giá trực tuyến DNSE OpenAPI KRX...</span>
                </div>
              )}

              {quoteResult && !isSearchingQuote && (
                <div className="p-4 rounded-xl border border-accent-blue/20 bg-accent-blue/5 space-y-3">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-0.5 rounded-md bg-accent-blue/20 text-accent-blue font-extrabold text-xs tracking-wider">
                          {quoteResult.ticker}
                        </span>
                        <span className="text-xs font-semibold text-text-secondary">
                          {getStockMetadata(quoteResult.ticker).sector}
                        </span>
                      </div>
                      <h4 className="text-xs font-bold text-text-primary mt-1">
                        {getStockMetadata(quoteResult.ticker).name}
                      </h4>
                    </div>

                    <div className="text-right">
                      <p className="text-base font-extrabold text-text-primary font-mono-num">
                        {formatVND(quoteResult.price)}
                      </p>
                      <div className="flex items-center justify-end gap-1 mt-0.5">
                        <span
                          className={`text-xs font-bold font-mono-num flex items-center gap-0.5 ${
                            quoteResult.change > 0
                              ? 'text-accent-emerald'
                              : quoteResult.change < 0
                              ? 'text-accent-rose'
                              : 'text-accent-gold'
                          }`}
                        >
                          {quoteResult.change > 0 ? (
                            <TrendingUp className="w-3 h-3" />
                          ) : quoteResult.change < 0 ? (
                            <TrendingDown className="w-3 h-3" />
                          ) : null}
                          {quoteResult.change >= 0 ? '+' : ''}
                          {quoteResult.change.toLocaleString('vi-VN')} đ (
                          {quoteResult.changePercent >= 0 ? '+' : ''}
                          {quoteResult.changePercent}%)
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="pt-2 border-t border-border-subtle/40 flex items-center justify-between text-[11px] text-text-muted">
                    <span>
                      Khối lượng: <strong className="text-text-secondary font-mono-num">{quoteResult.volume.toLocaleString('vi-VN')} CP</strong>
                    </span>
                    <span className="inline-flex items-center gap-1 text-accent-emerald font-semibold">
                      <span className="w-1.5 h-1.5 rounded-full bg-accent-emerald animate-pulse" />
                      Khớp lệnh thời gian thực DNSE
                    </span>
                  </div>
                </div>
              )}

              {/* Already in Watchlist notice */}
              {isAlreadyInWatchlist && searchTicker.length >= 3 && (
                <div className="p-3 rounded-xl border border-accent-gold/20 bg-accent-gold/10 flex items-center gap-2 text-xs text-accent-gold font-medium">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>Mã {searchTicker} đã có sẵn trong bảng theo dõi của bạn.</span>
                </div>
              )}

              {/* Error message */}
              {quoteError && !isSearchingQuote && (
                <div className="p-3 rounded-xl border border-accent-rose/20 bg-accent-rose/10 flex items-center gap-2 text-xs text-accent-rose font-medium">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{quoteError}</span>
                </div>
              )}

              {/* Actions */}
              <div className="flex justify-end gap-2.5 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowAddModal(false);
                    setSearchTicker('');
                    setQuoteResult(null);
                    setQuoteError(null);
                  }}
                  className="px-4 py-2 rounded-xl text-text-secondary hover:bg-surface-container-high font-semibold text-xs cursor-pointer transition-colors"
                >
                  Đóng
                </button>
                <button
                  type="submit"
                  disabled={!quoteResult || isAlreadyInWatchlist || isSearchingQuote || isAddingStock}
                  className="px-4 py-2 rounded-xl bg-accent-blue text-white font-bold text-xs hover:bg-accent-blue/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-sm active:scale-95 cursor-pointer flex items-center gap-1.5"
                >
                  {isAddingStock ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Đang thêm...</span>
                    </>
                  ) : (
                    <>
                      <Plus className="w-3.5 h-3.5" />
                      <span>Thêm Vào Bảng Theo Dõi</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Trading Drawer Slide Panel */}
      <TradingDrawer
        isOpen={tradeDrawerOpen}
        onClose={() => setTradeDrawerOpen(false)}
        valuation={valuation}
        initialTicker={activeTradeTicker}
        initialAction={activeTradeAction}
        onTradeSuccess={async () => {
          await onTradeSuccess();
        }}
      />
    </div>
  );
}
