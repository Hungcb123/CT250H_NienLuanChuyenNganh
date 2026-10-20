import { useState } from 'react';
import {
  Wallet,
  Receipt,
  LineChart,
  PiggyBank,
  Award,
  Bot,
  Activity,
  Sparkles,
  PanelLeftClose,
  PanelLeftOpen,
} from 'lucide-react';
import { TabType } from '../../types';
import logoWeb from '../../asset/logoWeb.png';

interface SidebarProps {
  activeTab: TabType;
  setActiveTab: (tab: TabType) => void;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
}

export function Sidebar({
  activeTab,
  setActiveTab,
  isCollapsed: controlledIsCollapsed,
  onToggleCollapse: controlledOnToggle,
}: SidebarProps) {
  const [internalCollapsed, setInternalCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem('sidebar_collapsed') === 'true';
    } catch {
      return false;
    }
  });

  const isCollapsed = controlledIsCollapsed !== undefined ? controlledIsCollapsed : internalCollapsed;

  const handleToggle = () => {
    if (controlledOnToggle) {
      controlledOnToggle();
    } else {
      setInternalCollapsed((prev) => {
        const next = !prev;
        try {
          localStorage.setItem('sidebar_collapsed', String(next));
        } catch {
          // ignore
        }
        return next;
      });
    }
  };

  const navItems: Array<{ id: TabType; label: string; icon: typeof Wallet }> = [
    { id: 'overview', label: 'Tổng quan tài sản', icon: Wallet },
    { id: 'market', label: 'Thị trường', icon: Activity },
    { id: 'ledger', label: 'Sổ giao dịch', icon: Receipt },
    { id: 'markowitz', label: 'Tối ưu danh mục', icon: LineChart },
    { id: 'taa', label: 'Tín hiệu thị trường', icon: Sparkles },
    { id: 'savings', label: 'Sổ tiết kiệm', icon: PiggyBank },
    { id: 'survey', label: 'Khảo sát', icon: Award },
    { id: 'copilot', label: 'Cố vấn', icon: Bot },
  ];

  const groups = [
    { label: 'Danh mục', ids: ['overview', 'ledger', 'savings'] },
    { label: 'Phân tích', ids: ['market', 'markowitz', 'taa'] },
    { label: 'Cá nhân', ids: ['survey', 'copilot'] },
  ];

  return (
    <aside aria-label="Điều hướng chính" className={`${isCollapsed ? 'w-20' : 'w-56'} fixed inset-y-0 left-0 z-40 hidden flex-col border-r border-border-subtle bg-surface-container-lowest md:flex transition-[width] duration-200 motion-reduce:transition-none`}>
      <div className={`flex h-14 shrink-0 items-center gap-2 border-b border-border-subtle ${isCollapsed ? 'justify-center px-2' : 'px-4'}`}>
        {!isCollapsed && <>
          <img src={logoWeb} alt="" className="h-8 w-8 rounded-lg object-cover" />
          <span className="flex-1 text-sm font-semibold tracking-tight text-text-primary">VNxCapital</span>
        </>}
        <button type="button" onClick={handleToggle} aria-expanded={!isCollapsed}
          aria-label={isCollapsed ? 'Mở rộng menu' : 'Thu gọn menu'} title={isCollapsed ? 'Mở rộng menu' : 'Thu gọn menu'}
          className="rounded-md p-2 text-text-secondary hover:bg-surface-container hover:text-text-primary">
          {isCollapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
        </button>
      </div>
      <nav className="flex-1 overflow-y-auto px-3 py-4">
        {groups.map((group, index) => <div key={group.label} className={index ? 'mt-5' : ''}>
          {!isCollapsed && <p className="mb-2 px-3 text-xs text-text-secondary">{group.label}</p>}
          {isCollapsed && index > 0 && <div className="mx-3 mb-3 border-t border-border-subtle" />}
          <div className="space-y-1">
            {group.ids.map(id => {
              const item = navItems.find(entry => entry.id === id)!;
              const Icon = item.icon;
              const selected = activeTab === item.id;
              return <button key={item.id} type="button" onClick={() => setActiveTab(item.id)}
                aria-current={selected ? 'page' : undefined} aria-label={item.label} title={isCollapsed ? item.label : undefined}
                className={`flex h-10 w-full items-center gap-3 rounded-md text-sm transition-colors ${isCollapsed ? 'justify-center' : 'px-3'} ${selected ? 'bg-accent-emerald-light font-semibold text-accent-emerald' : 'text-text-secondary hover:bg-surface-container-low hover:text-text-primary'}`}>
                <Icon className="h-4 w-4 shrink-0" strokeWidth={1.75} />
                {!isCollapsed && <span className="truncate">{item.label}</span>}
              </button>;
            })}
          </div>
        </div>)}
      </nav>
    </aside>
  );
}
