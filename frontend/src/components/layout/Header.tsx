import { RefreshCw } from 'lucide-react';
import { PortfolioValuation, UserProfile } from '../../types';
import { formatVND } from '../../utils/formatters';

interface HeaderProps {
  valuation: PortfolioValuation | null;
  profile: UserProfile | null;
  loading: boolean;
  onRefresh: () => void;
}

export function Header({ valuation, profile, loading, onRefresh }: HeaderProps) {
  return (
    <header className="h-16 px-8 bg-surface-container-lowest border-b border-border-subtle flex items-center justify-between sticky top-0 z-30">
      <div className="flex items-center gap-4">
        <span className="text-base font-bold text-text-primary tracking-tight">EquiFolio Wealth Terminal</span>
        <span className="text-xs px-2.5 py-0.5 rounded-full bg-surface-container border border-border-subtle text-text-muted font-medium">
          v1.0.0-PROD
        </span>
      </div>

      <div className="flex items-center gap-4">
        {/* Live NAV Status & Refresh */}
        <div className="hidden lg:flex items-center gap-2 px-3 py-1 rounded-full bg-surface-container border border-border-subtle shadow-2xs">
          <span className={`w-2 h-2 rounded-full ${loading ? 'bg-amber-500 animate-ping' : 'bg-accent-emerald'}`}></span>
          <span className="text-xs font-semibold text-text-secondary">
            NAV: {valuation ? formatVND(valuation.totalNetWorth) : '1,450,280,000 ₫'}
          </span>
          <button 
            onClick={onRefresh}
            disabled={loading}
            title="Làm mới dữ liệu từ API"
            className="ml-1 p-0.5 rounded hover:bg-surface-container-high transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-text-muted hover:text-accent-emerald ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {/* User Profile Capsule */}
        <div className="flex items-center gap-2 pl-3 border-l border-border-subtle">
          <div className="w-8 h-8 rounded-full bg-accent-emerald-light border border-accent-emerald/30 flex items-center justify-center text-accent-emerald font-bold text-xs">
            {profile ? profile.username.substring(0, 2).toUpperCase() : 'AN'}
          </div>
          <div className="text-left hidden sm:block">
            <p className="text-xs font-bold text-text-primary leading-tight">
              {profile ? profile.username : 'Alex Nguyen'}
            </p>
            <p className="text-[10px] text-accent-emerald font-semibold">
              {profile?.riskProfile || 'Private Wealth VIP'}
            </p>
          </div>
        </div>
      </div>
    </header>
  );
}
