import { useState, useEffect } from 'react';
import { RefreshCw, TrendingDown, TrendingUp, LogIn, LogOut, Sun, Moon } from 'lucide-react';
import { PortfolioValuation, UserProfile } from '../../types';
import { formatVND } from '../../utils/formatters';
import { VNINDEX_SUMMARY, VNIndexSummary } from '../../data/vnindexData';
import { useAuth } from '../../context/AuthContext';
import { useTheme } from '../../context/ThemeContext';
import { getVNIndexSummaryApi } from '../../services/api';

interface HeaderProps {
  valuation: PortfolioValuation | null;
  profile: UserProfile | null;
  loading: boolean;
  onRefresh: () => void;
  onOpenAuth: () => void;
}

export function Header({ valuation, profile, loading, onRefresh, onOpenAuth }: HeaderProps) {
  const { isAuthenticated, logout, user } = useAuth();
  const { isDark, toggleTheme } = useTheme();
  const [indexData, setIndexData] = useState<VNIndexSummary>(VNINDEX_SUMMARY);

  useEffect(() => {
    getVNIndexSummaryApi().then(data => {
      if (data && data.currentPoints) {
        setIndexData({
          latestDate: data.latestDate,
          currentPoints: data.currentPoints,
          changePoints: data.changePoints,
          changePercent: data.changePercent,
          high52w: data.high52w,
          low52w: data.low52w,
          avgVolume20: data.avgVolume20,
          latestVolume: data.latestVolume,
          ma20: data.ma20,
          ma50: data.ma50
        });
      }
    });
  }, [loading]);

  const isPos = indexData.changePercent >= 0;
  const currentProfile = user || profile;

  return (
    <header className="h-16 px-6 lg:px-8 bg-surface-container-lowest/95 backdrop-blur-md border-b border-border-subtle flex items-center justify-between sticky top-0 z-30 shadow-[0_1px_3px_rgba(0,0,0,0.12)] transition-colors duration-200">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-accent-emerald"></span>
          <span className="text-sm font-extrabold text-text-primary tracking-tight">EquiFolio Wealth Terminal</span>
        </div>

        {/* Live VN-Index Status Chip (DNSE Market Data) */}
        <div className="hidden md:flex items-center gap-2 px-3 py-1 rounded-lg bg-surface-container-low border border-border-subtle text-xs" title={`Dữ liệu thị trường DNSE KRX (${indexData.latestDate})`}>
          <span className="text-text-muted font-medium">VN-Index</span>
          <span className="font-bold text-text-primary font-mono-num">{indexData.currentPoints.toFixed(2)}</span>
          <span className={`text-[11px] font-bold font-mono-num flex items-center ${isPos ? 'text-accent-emerald' : 'text-accent-rose'}`}>
            {isPos ? <TrendingUp className="w-3 h-3 inline mr-0.5" /> : <TrendingDown className="w-3 h-3 inline mr-0.5" />}
            {isPos ? '+' : ''}{indexData.changePercent.toFixed(2)}%
          </span>
          <span className="text-[10px] text-text-muted font-mono-num">({indexData.changePoints >= 0 ? '+' : ''}{indexData.changePoints.toFixed(2)})</span>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {/* Live NAV Status & Refresh */}
        <div className="hidden lg:flex items-center gap-2.5 px-3 py-1.5 rounded-lg bg-surface-container-low border border-border-subtle">
          <span className="w-2 h-2 rounded-full bg-accent-emerald"></span>
          <span className="text-xs text-text-muted font-medium">NAV:</span>
          <span className="text-xs font-bold font-mono-num text-text-primary">
            {valuation ? formatVND(valuation.totalNetWorth) : '0 ₫'}
          </span>
          <button 
            onClick={onRefresh}
            disabled={loading}
            title="Làm mới dữ liệu từ API"
            className="ml-1 p-1 rounded-md hover:bg-surface-container-high text-text-muted hover:text-accent-emerald transition-colors cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-accent-emerald' : ''}`} />
          </button>
        </div>

        {/* Theme Mode Toggle (TCInvest Darkmode vs White mode) */}
        <button
          onClick={toggleTheme}
          className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-surface-container-low hover:bg-surface-container border border-border-subtle text-text-primary text-xs font-semibold transition-all cursor-pointer shadow-xs group"
          title={isDark ? "Chuyển sang White Mode (Chế độ Sáng)" : "Chuyển sang Dark Mode (Chế độ Tối TCInvest)"}
        >
          {isDark ? (
            <>
              <Moon className="w-3.5 h-3.5 text-accent-gold transition-transform group-hover:-rotate-12" />
              <span className="text-[11px] font-bold text-text-secondary group-hover:text-text-primary">Tối</span>
            </>
          ) : (
            <>
              <Sun className="w-3.5 h-3.5 text-amber-500 transition-transform group-hover:rotate-45" />
              <span className="text-[11px] font-bold text-text-secondary group-hover:text-text-primary">Sáng</span>
            </>
          )}
        </button>

        {/* User Auth Capsule */}
        {isAuthenticated && currentProfile ? (
          <div className="flex items-center gap-3 pl-2 border-l border-border-subtle">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-surface-container-high border border-border-subtle flex items-center justify-center text-text-primary font-bold text-xs uppercase shadow-2xs">
                {currentProfile.username.substring(0, 2)}
              </div>
              <div className="text-left hidden sm:flex items-center gap-1.5">
                <span className="text-xs font-bold text-text-primary leading-tight">
                  {currentProfile.username}
                </span>
                <span className="text-[10px] text-text-muted font-bold px-1.5 py-0.2 bg-surface-container rounded border border-border-subtle uppercase">
                  VIP
                </span>
              </div>
            </div>

            <button
              onClick={() => {
                if (window.confirm("Bạn có chắc chắn muốn đăng xuất?")) {
                  logout();
                  onRefresh();
                }
              }}
              title="Đăng xuất khỏi hệ thống"
              className="p-1.5 rounded-lg text-text-muted hover:text-accent-rose hover:bg-accent-rose-light transition-colors cursor-pointer"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-2 pl-2 border-l border-border-subtle">
            <button
              onClick={onOpenAuth}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-accent-emerald hover:opacity-90 text-white font-bold text-xs shadow-xs hover:shadow-sm transition-all cursor-pointer"
            >
              <LogIn className="w-3.5 h-3.5" />
              <span>Đăng nhập</span>
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
