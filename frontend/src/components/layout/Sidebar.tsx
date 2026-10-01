import { Shield, Wallet, Receipt, LineChart, PiggyBank, Award, Bot } from 'lucide-react';
import { TabType } from '../../types';

interface SidebarProps {
  activeTab: TabType;
  setActiveTab: (tab: TabType) => void;
}

export function Sidebar({ activeTab, setActiveTab }: SidebarProps) {
  const navItems: Array<{ id: TabType; label: string; icon: typeof Wallet }> = [
    { id: 'overview', label: 'Tổng quan tài sản', icon: Wallet },
    { id: 'ledger', label: 'Sổ cái kép ACID', icon: Receipt },
    { id: 'markowitz', label: 'Tối ưu Markowitz', icon: LineChart },
    { id: 'savings', label: 'Sổ tiết kiệm & Lãi kép', icon: PiggyBank },
    { id: 'survey', label: 'Khảo sát rủi ro (SAA)', icon: Award },
    { id: 'copilot', label: 'AI Copilot Cố vấn', icon: Bot },
  ];

  return (
    <aside className="w-72 bg-surface-container-lowest border-r border-border-subtle flex flex-col justify-between h-screen fixed top-0 left-0 z-40 select-none">
      <div className="p-6">
        {/* Brand Header */}
        <div className="flex items-center gap-3 pb-6 border-b border-border-subtle">
          <div className="w-10 h-10 rounded-lg bg-surface-container flex items-center justify-center border border-border-subtle shadow-sm text-accent-emerald">
            <Shield className="w-6 h-6 fill-accent-emerald/20 text-accent-emerald" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-text-primary tracking-tight">EquiFolio</h1>
            <p className="text-[11px] text-text-muted uppercase tracking-wider font-semibold">Swiss Wealth Architecture</p>
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
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-semibold transition-all ${
                  isActive
                    ? 'bg-surface-container-low text-text-primary border-l-4 border-accent-emerald shadow-sm'
                    : 'text-text-secondary hover:text-text-primary hover:bg-surface-container-low'
                }`}
              >
                <Icon className={`w-5 h-5 ${isActive ? 'text-accent-emerald' : 'text-text-muted'}`} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* Sidebar Footer */}
      <div className="p-6 border-t border-border-subtle bg-surface-container-low/40">
        <div className="p-3 rounded-lg border border-border-subtle bg-surface-container-lowest mb-3 shadow-xs">
          <div className="flex items-center gap-2 text-xs font-semibold text-text-primary">
            <span className="w-2 h-2 rounded-full bg-accent-emerald animate-pulse"></span>
            <span>PostgreSQL 16 + pgvector</span>
          </div>
          <p className="text-[11px] text-text-muted mt-1">Lõi Sổ cái kép ACID sẵn sàng</p>
        </div>
        <p className="text-[11px] text-text-muted text-center font-medium">CT250H • Niên Luận Chuyên Ngành</p>
      </div>
    </aside>
  );
}
