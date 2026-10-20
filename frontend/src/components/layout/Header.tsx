import { useEffect, useRef, useState } from 'react';
import { RefreshCw, LogIn, LogOut, Sun, Moon, ChevronDown } from 'lucide-react';
import { TabType, UserProfile } from '../../types';
import { useAuth } from '../../context/AuthContext';
import { useTheme } from '../../context/ThemeContext';

interface HeaderProps {
  activeTab: TabType;
  profile: UserProfile | null;
  loading: boolean;
  onRefresh: () => void;
  onOpenAuth: () => void;
}

const titles: Record<TabType, string> = {
  overview: 'Tổng quan tài sản', market: 'Thị trường', ledger: 'Sổ giao dịch',
  markowitz: 'Tối ưu danh mục', taa: 'Tín hiệu thị trường', savings: 'Sổ tiết kiệm',
  survey: 'Khảo sát', copilot: 'Cố vấn',
};

export function Header({ activeTab, profile, loading, onRefresh, onOpenAuth }: HeaderProps) {
  const { isAuthenticated, logout, user } = useAuth();
  const { isDark, toggleTheme } = useTheme();
  const currentProfile = user || profile;
  const [accountOpen, setAccountOpen] = useState(false);
  const accountRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!accountOpen) return;
    const dismiss = (event: MouseEvent) => {
      if (!accountRef.current?.contains(event.target as Node)) setAccountOpen(false);
    };
    document.addEventListener('mousedown', dismiss);
    return () => document.removeEventListener('mousedown', dismiss);
  }, [accountOpen]);
  const toolClass = 'inline-flex h-9 w-9 items-center justify-center rounded-md text-text-secondary hover:bg-surface-container hover:text-text-primary disabled:opacity-50';
  return (
    <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center justify-between gap-3 border-b border-border-subtle bg-surface-container-lowest px-4 sm:px-8">
      <span className="min-w-0 truncate text-sm font-medium text-text-primary">{titles[activeTab]}</span>
      <div className="flex shrink-0 items-center gap-1">
        <button type="button" onClick={onRefresh} disabled={loading} aria-label="Làm mới dữ liệu" title="Làm mới dữ liệu" className={toolClass}>
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
        <button type="button" onClick={toggleTheme} aria-label={isDark ? 'Chuyển sang giao diện sáng' : 'Chuyển sang giao diện tối'}
          title={isDark ? 'Chuyển sang giao diện sáng' : 'Chuyển sang giao diện tối'} className={toolClass}>
          {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>
        {isAuthenticated && currentProfile ? (
          <div ref={accountRef} className="relative ml-2 border-l border-border-subtle pl-3"
            onKeyDown={event => { if (event.key === 'Escape') { setAccountOpen(false); triggerRef.current?.focus(); } }}>
            <button ref={triggerRef} type="button" aria-expanded={accountOpen} aria-controls="account-actions" aria-label={`Tài khoản ${currentProfile.username}`}
              onClick={() => setAccountOpen(open => !open)} className="flex h-9 items-center gap-2 rounded-md px-1.5 text-sm text-text-primary hover:bg-surface-container">
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-surface-container-high text-xs font-semibold uppercase">{currentProfile.username.substring(0, 2)}</span>
              <span className="hidden max-w-44 truncate sm:block">{currentProfile.username}</span>
              <ChevronDown className="h-3.5 w-3.5 text-text-secondary" />
            </button>
            {accountOpen && <div id="account-actions" className="absolute right-0 top-full mt-2 w-60 rounded-lg border border-border-subtle bg-surface-container-lowest p-1 shadow-lg">
              <p className="truncate border-b border-border-subtle px-3 py-2 text-xs text-text-secondary">{currentProfile.username}</p>
              <button type="button" onClick={() => {
                setAccountOpen(false);
                if (window.confirm('Bạn có chắc chắn muốn đăng xuất?')) { logout(); onRefresh(); }
              }} className="flex w-full items-center gap-2 rounded-md px-3 py-2.5 text-left text-sm text-text-primary hover:bg-surface-container">
                <LogOut className="h-4 w-4" />Đăng xuất
              </button>
            </div>}
          </div>
        ) : <button type="button" onClick={onOpenAuth} className="ml-2 inline-flex items-center gap-2 rounded-md bg-accent-emerald px-3 py-2 text-xs font-semibold text-white hover:opacity-90"><LogIn className="h-4 w-4" />Đăng nhập</button>}
      </div>
    </header>
  );
}
