import { Shield, Wallet, Receipt, LineChart, PiggyBank, Award, Bot, Activity, Sparkles } from 'lucide-react';
import { TabType } from '../../types';

interface SidebarProps {
  activeTab: TabType;
  setActiveTab: (tab: TabType) => void;
}

export function Sidebar({ activeTab, setActiveTab }: SidebarProps) {
  const navItems: Array<{ id: TabType; label: string; icon: typeof Wallet }> = [
    { id: 'overview', label: 'Tổng quan tài sản', icon: Wallet },
    { id: 'market', label: 'Thị trường & VN-Index', icon: Activity },
    { id: 'ledger', label: 'Sổ cái kép ACID', icon: Receipt },
    { id: 'markowitz', label: 'Tối ưu Markowitz', icon: LineChart },
    { id: 'taa', label: 'Phân bổ chiến thuật (TAA)', icon: Sparkles },
    { id: 'savings', label: 'Sổ tiết kiệm & Lãi kép', icon: PiggyBank },
    { id: 'survey', label: 'Khảo sát rủi ro (SAA)', icon: Award },
    { id: 'copilot', label: 'AI Copilot Cố vấn', icon: Bot },
  ];

  return (
    <aside className="w-72 bg-surface-container-lowest border-r border-border-subtle flex flex-col justify-between h-screen fixed top-0 left-0 z-40 select-none shadow-[1px_0_4px_rgba(0,0,0,0.15)] transition-colors duration-200">
      <div className="p-6">
        {/* Brand Header */}
        <div className="flex items-center gap-3.5 pb-6 border-b border-border-subtle">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-emerald-700 flex items-center justify-center shadow-md shadow-emerald-900/30 text-white ring-1 ring-emerald-400/30">
            <Shield className="w-5 h-5 fill-white/20 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <h1 className="text-lg font-extrabold text-text-primary tracking-tight">EquiFolio</h1>
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-surface-container text-text-muted border border-border-subtle">CH</span>
            </div>
            <p className="text-[10px] text-text-muted uppercase tracking-widest font-semibold mt-0.5">Swiss Wealth Architecture</p>
          </div>
        </div>

        {/* Navigation Items */}
        <nav className="mt-6 space-y-1.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-xs font-semibold transition-all duration-150 cursor-pointer ${
                  isActive
                    ? 'bg-surface-container-high text-accent-emerald font-bold border border-accent-emerald/30 shadow-xs'
                    : 'text-text-secondary hover:text-text-primary hover:bg-surface-container-low border border-transparent'
                }`}
              >
                <Icon className={`w-4 h-4 transition-colors ${isActive ? 'text-accent-emerald' : 'text-text-muted'}`} />
                <span className="flex-1 text-left">{item.label}</span>
                {isActive && (
                  <span className="w-1.5 h-1.5 rounded-full bg-accent-emerald shadow-[0_0_8px_rgba(0,192,135,0.8)]"></span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Sidebar Footer */}
      <div className="p-4 border-t border-border-subtle bg-surface-container-low/40">
        <div className="flex items-center justify-between px-2 py-1 text-xs text-text-muted">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-accent-emerald"></span>
            <span className="font-semibold text-text-secondary text-[11px]">Hệ thống trực tuyến</span>
          </div>
          <span className="text-[10px] font-mono text-text-muted">v2.4 Pro</span>
        </div>
        <p className="text-[10px] text-text-muted text-center mt-2 font-medium">EquiFolio Wealth Terminal</p>
      </div>
    </aside>
  );
}
