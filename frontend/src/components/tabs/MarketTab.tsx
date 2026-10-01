import { useState, useMemo } from 'react';
import {
  TrendingUp, TrendingDown, Search, Filter, ShieldAlert, BarChart3,
  Layers, ArrowUpRight, ArrowDownRight, Activity
} from 'lucide-react';
import { VNIndexChart } from '../charts/VNIndexChart';
import {
  VNINDEX_SUMMARY,
  VN30_WATCHLIST
} from '../../data/vnindexData';
import { formatVND } from '../../utils/formatters';

export function MarketTab() {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedSector, setSelectedSector] = useState<string>('ALL');

  // Extract unique sectors
  const sectors = useMemo(() => {
    const s = new Set<string>();
    VN30_WATCHLIST.forEach(item => s.add(item.sector));
    return ['ALL', ...Array.from(s)];
  }, []);

  // Filter watchlist
  const filteredWatchlist = useMemo(() => {
    return VN30_WATCHLIST.filter(item => {
      const matchSearch =
        item.ticker.toLowerCase().includes(searchTerm.toLowerCase()) ||
        item.name.toLowerCase().includes(searchTerm.toLowerCase());
      const matchSector = selectedSector === 'ALL' || item.sector === selectedSector;
      return matchSearch && matchSector;
    });
  }, [searchTerm, selectedSector]);

  // Market Breadth Stats
  const breadth = useMemo(() => {
    let advances = 0;
    let declines = 0;
    let unchanged = 0;
    VN30_WATCHLIST.forEach(i => {
      if (i.changePercent > 0) advances++;
      else if (i.changePercent < 0) declines++;
      else unchanged++;
    });
    return { advances, declines, unchanged };
  }, []);

  return (
    <div className="space-y-6">
      {/* 1. Header Banner */}
      <section className="bg-surface-container-lowest border border-border-subtle rounded-xl p-6 shadow-sm flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold text-text-primary tracking-tight">Thị Trường Chứng Khoán & Chỉ Số VN-Index</h2>
            <span className="px-2.5 py-0.5 rounded-full bg-accent-emerald-light text-accent-emerald text-xs font-semibold border border-accent-emerald/20">
              HOSE Realtime Feeds
            </span>
            <span className="px-2.5 py-0.5 rounded-full bg-surface-container-high text-text-secondary text-xs font-medium">
              30 Cổ Phiếu Rổ VN30 + 3 ETFs
            </span>
          </div>
          <p className="text-xs text-text-secondary mt-1">
            Dữ liệu nến ngày đồng bộ từ VNDirect API & Yahoo Finance phục vụ dự báo chu kỳ LightGBM ONNX
          </p>
        </div>

        {/* Cross-Asset Macro Indicator Badge */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2.5 px-3.5 py-2 rounded-lg bg-surface-container-low border border-border-subtle">
            <ShieldAlert className="w-4 h-4 text-accent-gold" />
            <div className="text-left">
              <p className="text-[10px] uppercase font-bold text-text-muted tracking-wider">Tỷ Lệ Vĩ Mô Vàng / VN-Index</p>
              <p className="text-xs font-bold text-text-primary">
                48.0 <span className="text-accent-emerald font-semibold">(Vùng an toàn • Chưa có rủi ro tháo chạy)</span>
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* 2. Market Barometer Cards */}
      <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
        {/* Card 1: VN-Index */}
        <div className="bg-surface-container-lowest border border-border-subtle rounded-xl p-5 shadow-sm hover:border-border-highlight transition-all">
          <div className="flex items-center justify-between text-text-muted mb-2">
            <span className="text-xs uppercase tracking-wider font-semibold">Chỉ số VN-Index</span>
            <Activity className="w-5 h-5 text-accent-emerald" />
          </div>
          <div className="text-2xl font-black text-text-primary tracking-tight">
            {VNINDEX_SUMMARY.currentPoints.toLocaleString('vi-VN', { minimumFractionDigits: 2 })}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs">
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-accent-rose-light text-accent-rose font-bold">
              <TrendingDown className="w-3.5 h-3.5" /> {VNINDEX_SUMMARY.changePoints.toFixed(2)} ({VNINDEX_SUMMARY.changePercent.toFixed(2)}%)
            </span>
            <span className="text-text-muted">{(VNINDEX_SUMMARY.latestVolume / 1e6).toFixed(1)}M CP</span>
          </div>
        </div>

        {/* Card 2: VN30 Index */}
        <div className="bg-surface-container-lowest border border-border-subtle rounded-xl p-5 shadow-sm hover:border-border-highlight transition-all">
          <div className="flex items-center justify-between text-text-muted mb-2">
            <span className="text-xs uppercase tracking-wider font-semibold">Chỉ số VN30</span>
            <Layers className="w-5 h-5 text-secondary" />
          </div>
          <div className="text-2xl font-black text-text-primary tracking-tight">
            1,805.12
          </div>
          <div className="mt-3 flex items-center justify-between text-xs">
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-accent-rose-light text-accent-rose font-bold">
              <TrendingDown className="w-3.5 h-3.5" /> -15.20 (-0.83%)
            </span>
            <span className="text-text-muted">Độ lệch: +55.82 đ</span>
          </div>
        </div>

        {/* Card 3: Market Breadth */}
        <div className="bg-surface-container-lowest border border-border-subtle rounded-xl p-5 shadow-sm hover:border-border-highlight transition-all">
          <div className="flex items-center justify-between text-text-muted mb-2">
            <span className="text-xs uppercase tracking-wider font-semibold">Độ Rộng Rổ VN30</span>
            <BarChart3 className="w-5 h-5 text-accent-gold" />
          </div>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-sm font-bold text-accent-emerald flex items-center">
              <ArrowUpRight className="w-4 h-4" /> {breadth.advances} Tăng
            </span>
            <span className="text-text-muted">•</span>
            <span className="text-sm font-bold text-accent-rose flex items-center">
              <ArrowDownRight className="w-4 h-4" /> {breadth.declines} Giảm
            </span>
            <span className="text-text-muted">•</span>
            <span className="text-sm font-bold text-text-secondary">
              {breadth.unchanged} TC
            </span>
          </div>
          <div className="w-full bg-slate-100 h-2 rounded-full mt-3 overflow-hidden flex">
            <div style={{ width: `${(breadth.advances / VN30_WATCHLIST.length) * 100}%` }} className="bg-accent-emerald h-full"></div>
            <div style={{ width: `${(breadth.unchanged / VN30_WATCHLIST.length) * 100}%` }} className="bg-amber-400 h-full"></div>
            <div style={{ width: `${(breadth.declines / VN30_WATCHLIST.length) * 100}%` }} className="bg-accent-rose h-full"></div>
          </div>
        </div>

        {/* Card 4: Technical Trend */}
        <div className="bg-surface-container-lowest border border-border-subtle rounded-xl p-5 shadow-sm hover:border-border-highlight transition-all">
          <div className="flex items-center justify-between text-text-muted mb-2">
            <span className="text-xs uppercase tracking-wider font-semibold">Xu Hướng Kỹ Thuật</span>
            <span className="text-[10px] font-bold text-accent-emerald bg-accent-emerald-light px-1.5 py-0.5 rounded">LightGBM</span>
          </div>
          <div className="space-y-1.5 mt-1 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-text-secondary">MA20 (Ngắn hạn):</span>
              <strong className="text-text-primary">{VNINDEX_SUMMARY.ma20.toFixed(1)}</strong>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-text-secondary">MA50 (Trung hạn):</span>
              <strong className="text-text-primary">{VNINDEX_SUMMARY.ma50.toFixed(1)}</strong>
            </div>
            <div className="flex items-center justify-between pt-1 border-t border-border-subtle">
              <span className="text-text-secondary">Chu kỳ T+20:</span>
              <span className="font-bold text-accent-emerald">+1 Bullish (Tích lũy)</span>
            </div>
          </div>
        </div>
      </section>

      {/* 3. Dedicated Interactive VN-Index Technical Chart */}
      <section className="bg-surface-container-lowest border border-border-subtle rounded-xl p-6 shadow-sm">
        <div className="mb-4">
          <h3 className="text-sm font-bold text-text-primary uppercase tracking-wider">
            Biểu Đồ Kỹ Thuật Chỉ Số VN-Index (VNDirect Benchmark)
          </h3>
          <p className="text-xs text-text-secondary mt-0.5">
            Dữ liệu chuỗi thời gian 1,430 phiên giao dịch từ 2021 đến nay với đường MA20, MA50 và khối lượng khớp lệnh
          </p>
        </div>

        <VNIndexChart height={340} showControls={true} />
      </section>

      {/* 4. VN30 Live Watchlist Table */}
      <section className="bg-surface-container-lowest border border-border-subtle rounded-xl p-6 shadow-sm space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h3 className="text-sm font-bold text-text-primary uppercase tracking-wider">
              Bảng Giá Theo Dõi 30 Cổ Phiếu Rổ VN30 & Quỹ ETF
            </h3>
            <p className="text-xs text-text-secondary">
              Nguồn cấp dữ liệu cho thuật toán Tối ưu hóa Markowitz MVO (Lô chẵn 100 cp)
            </p>
          </div>

          {/* Search Box */}
          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="w-4 h-4 text-text-muted absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Tìm mã cổ phiếu hoặc tên công ty..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-9 pr-3 py-1.5 text-xs rounded-lg border border-border-subtle bg-surface-container-low text-text-primary focus:outline-none focus:border-accent-emerald w-64"
              />
            </div>
          </div>
        </div>

        {/* Sector Tabs */}
        <div className="flex flex-wrap items-center gap-1.5 pt-1 border-b border-border-subtle pb-3 text-xs">
          <span className="text-[11px] font-semibold text-text-muted mr-1 flex items-center gap-1">
            <Filter className="w-3 h-3" /> Nhóm ngành:
          </span>
          {sectors.map((sec) => (
            <button
              key={sec}
              type="button"
              onClick={() => setSelectedSector(sec)}
              className={`px-2.5 py-1 rounded-full text-xs font-semibold transition-all ${
                selectedSector === sec
                  ? 'bg-accent-emerald text-white shadow-xs'
                  : 'bg-surface-container-low text-text-secondary hover:text-text-primary hover:bg-surface-container'
              }`}
            >
              {sec === 'ALL' ? 'Tất cả' : sec}
            </button>
          ))}
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-border-subtle text-text-muted uppercase text-[11px]">
                <th className="pb-3 font-semibold">Mã CP</th>
                <th className="pb-3 font-semibold">Tên Doanh Nghiệp</th>
                <th className="pb-3 font-semibold">Nhóm Ngành</th>
                <th className="pb-3 font-semibold text-right">Giá Thị Trường</th>
                <th className="pb-3 font-semibold text-right">Biến Động 1D</th>
                <th className="pb-3 font-semibold text-right">Khối Lượng</th>
                <th className="pb-3 font-semibold text-center">Tín Hiệu ONNX</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle">
              {filteredWatchlist.map((item) => {
                const isPos = item.changePercent > 0;
                const isNeg = item.changePercent < 0;
                return (
                  <tr key={item.rawTicker} className="hover:bg-surface-container-low transition-colors">
                    <td className="py-3 font-bold text-text-primary">
                      <span className="px-2 py-0.5 rounded bg-surface-container font-mono text-xs">
                        {item.ticker}
                      </span>
                    </td>
                    <td className="py-3 text-text-primary font-medium">{item.name}</td>
                    <td className="py-3 text-text-secondary">
                      <span className="px-2 py-0.5 rounded bg-surface-container-low text-[11px] font-medium border border-border-subtle">
                        {item.sector}
                      </span>
                    </td>
                    <td className="py-3 text-right font-mono font-bold text-text-primary">
                      {item.rawTicker.includes('GC=F')
                        ? `$${item.price.toFixed(2)}`
                        : formatVND(item.price)}
                    </td>
                    <td className="py-3 text-right font-mono font-bold">
                      <span className={`inline-flex items-center gap-0.5 ${
                        isPos ? 'text-accent-emerald' : isNeg ? 'text-accent-rose' : 'text-text-muted'
                      }`}>
                        {isPos ? <TrendingUp className="w-3.5 h-3.5" /> : isNeg ? <TrendingDown className="w-3.5 h-3.5" /> : null}
                        {item.changePercent > 0 ? '+' : ''}{item.changePercent.toFixed(2)}%
                      </span>
                    </td>
                    <td className="py-3 text-right font-mono text-text-secondary">
                      {item.volume.toLocaleString('vi-VN')}
                    </td>
                    <td className="py-3 text-center">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                        item.signal === 'BULLISH'
                          ? 'bg-accent-emerald-light text-accent-emerald'
                          : item.signal === 'BEARISH'
                          ? 'bg-accent-rose-light text-accent-rose'
                          : 'bg-surface-container text-text-muted'
                      }`}>
                        {item.signal === 'BULLISH' ? '+1 Tích cực' : item.signal === 'BEARISH' ? '-1 Thận trọng' : '0 Trung lập'}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
