import { useState, useEffect } from 'react';
import { TabType, PortfolioValuation, RebalancePlan, UserProfile } from './types';
import { getPortfolioValuation, getRebalancePlan, getUserProfile, executeRebalancePlan } from './services/api';
import { Sidebar } from './components/layout/Sidebar';
import { Header } from './components/layout/Header';
import { OverviewTab } from './components/tabs/OverviewTab';
import { MarketTab } from './components/tabs/MarketTab';
import { LedgerTab } from './components/tabs/LedgerTab';
import { ResearchWorkbench } from './components/tabs/ResearchWorkbench';
import { MarkowitzTab } from './components/tabs/MarkowitzTab';
import { TaaTab } from './components/tabs/TaaTab';
import { SavingsTab } from './components/tabs/SavingsTab';
import { SurveyTab } from './components/tabs/SurveyTab';
import { CopilotTab } from './components/tabs/CopilotTab';
import { AuthModal } from './components/auth/AuthModal';
import { RebalanceConfirmModal } from './components/trading/RebalanceConfirmModal';
import { useAuth } from './context/AuthContext';
import { useToast } from './context/ToastContext';

export default function App() {
  const { user: authUser, isAuthenticated } = useAuth();
  const toast = useToast();
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [valuation, setValuation] = useState<PortfolioValuation | null>(null);
  const [plan, setPlan] = useState<RebalancePlan | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [confirmedExecution, setConfirmedExecution] = useState(false);
  const [executingRebalance, setExecutingRebalance] = useState(false);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [isRebalanceModalOpen, setIsRebalanceModalOpen] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem('sidebar_collapsed') === 'true';
    } catch {
      return false;
    }
  });

  const toggleSidebar = () => {
    setIsSidebarCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem('sidebar_collapsed', String(next));
      } catch {
        // ignore
      }
      return next;
    });
  };

  // Survey state (5 questions: 0, 7, 14, 20)
  const [surveyScores, setSurveyScores] = useState<number[]>([14, 14, 14, 14, 12]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [valData, planData, profData] = await Promise.all([
        getPortfolioValuation(),
        getRebalancePlan(),
        getUserProfile(),
      ]);
      setValuation(valData);
      setPlan(planData);
      setProfile(profData);
      if (planData?.driftDetected) {
        setConfirmedExecution(false);
      }
    } catch (e) {
      console.error("Failed to load portfolio data", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [isAuthenticated]);

  const handleOpenRebalanceModal = () => {
    if (!isAuthenticated) {
      setIsAuthModalOpen(true);
      toast.warning(
        "Vui lòng đăng nhập để thực hiện tái cơ cấu danh mục tài sản.",
        "Yêu cầu xác thực danh tính"
      );
      return;
    }
    setIsRebalanceModalOpen(true);
  };

  const handleExecuteActualRebalance = async () => {
    setExecutingRebalance(true);
    try {
      if (!plan?.planToken) throw new Error('Vui lòng tải lại và xem kế hoạch trước khi xác nhận.');
      const res = await executeRebalancePlan(plan.planToken);
      setConfirmedExecution(res.updatedPlan?.driftDetected === false);
      setIsRebalanceModalOpen(false);
      await loadData();
      toast.success(
        res.message || "Hệ thống Sổ cái kép đã ghi nhận bút toán tái cơ cấu! Trạng thái danh mục đã được cân bằng lại.",
        "Tái cơ cấu thành công"
      );
    } catch (err: any) {
      const errorMsg = err.message || String(err);
      if (
        errorMsg.includes("đăng nhập") ||
        errorMsg.includes("401") ||
        errorMsg.includes("Unauthorized")
      ) {
        setIsRebalanceModalOpen(false);
        setIsAuthModalOpen(true);
        toast.warning(
          "Vui lòng đăng nhập để thực hiện tái cơ cấu danh mục tài sản.",
          "Yêu cầu xác thực danh tính"
        );
      } else {
        toast.error(errorMsg, "Lỗi thực thi tái cơ cấu");
        setIsRebalanceModalOpen(false);
        await loadData();
      }
    } finally {
      setExecutingRebalance(false);
    }
  };

  const activeUserProfile = authUser || profile;

  return (
    <div className="min-h-screen bg-surface flex text-text-primary">
      {/* 1. Global Navigation Sidebar */}
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        isCollapsed={isSidebarCollapsed}
        onToggleCollapse={toggleSidebar}
      />

      {/* 2. Main Content Wrapper */}
      <div
        className={`${
          isSidebarCollapsed ? 'md:ml-20' : 'md:ml-56'
        } transition-all duration-300 ease-in-out min-w-0 flex-1 flex flex-col min-h-screen`}
      >
        <Header
          activeTab={activeTab}
          profile={activeUserProfile}
          loading={loading}
          onRefresh={loadData}
          onOpenAuth={() => setIsAuthModalOpen(true)}
        />

        <main className={`vnx-workspace px-4 pb-4 sm:px-8 sm:pb-8 ${activeTab === 'overview' ? 'pt-4' : 'pt-4 sm:pt-8'} flex flex-col gap-6 flex-1 min-w-0`}>
          <label className="block md:hidden text-sm text-text-primary space-y-2">
            <span>Chuyển mục</span>
            <select value={activeTab} onChange={event => setActiveTab(event.target.value as TabType)} className="w-full rounded-lg bg-surface-container-low border border-border-subtle px-3 py-2">
              <option value="overview">Tổng quan tài sản</option><option value="market">Thị trường</option>
              <option value="ledger">Sổ giao dịch</option><option value="markowitz">Tối ưu danh mục</option>
              <option value="taa">Tín hiệu thị trường</option><option value="savings">Sổ tiết kiệm</option>
              <option value="survey">Khảo sát</option><option value="copilot">Cố vấn</option>
            </select>
          </label>
          {activeUserProfile?.email === `${activeUserProfile?.username}@demo.equifolio.test` &&
            ['demo_balanced', 'demo_growth', 'demo_defensive'].includes(activeUserProfile?.username ?? '') && (
              <p role="status" className="rounded-lg border border-border-subtle bg-surface-container-low px-4 py-3 text-sm text-text-primary">
                <strong>Tài khoản demo.</strong> Lịch sử danh mục, giao dịch và chỉ số hiệu suất là dữ liệu mô phỏng để kiểm thử.
              </p>
          )}
          {activeTab === 'overview' && (
            <OverviewTab
              valuation={valuation}
              plan={plan}
              profile={activeUserProfile}
              confirmedExecution={confirmedExecution}
              onConfirmRebalance={handleOpenRebalanceModal}
              executing={executingRebalance}
              onNavigateToSurvey={() => setActiveTab('survey')}
              onTradeSuccess={loadData}
            />
          )}

          {activeTab === 'market' && (
            <MarketTab
              plan={plan}
              valuation={valuation}
              onTradeSuccess={loadData}
              onNavigateTab={(tab) => setActiveTab(tab as TabType)}
            />
          )}

          {activeTab === 'ledger' && <LedgerTab onRefresh={loadData} />}

          {activeTab === 'markowitz' && (
            <div className="space-y-6"><ResearchWorkbench key={authUser?.id ?? 'guest'} />
            <details><summary className="cursor-pointer text-sm text-text-secondary py-3">Minh họa lý thuyết — các tham số giả định, không dùng để đặt lệnh</summary>
            <MarkowitzTab
              plan={plan}
              profile={activeUserProfile}
              valuation={valuation}
              onConfirmRebalance={handleOpenRebalanceModal}
              confirmedExecution={confirmedExecution}
              executing={executingRebalance}
              onRefreshData={loadData}
            /></details></div>
          )}

          {activeTab === 'taa' && (
            <TaaTab
              plan={plan}
              profile={activeUserProfile}
              valuation={valuation}
              onRefreshData={async () => { setConfirmedExecution(false); await loadData(); }}
              onConfirmRebalance={handleOpenRebalanceModal}
              executing={executingRebalance}
            />
          )}

          {activeTab === 'savings' && <SavingsTab onRefresh={loadData} />}

          {activeTab === 'survey' && (
            <SurveyTab
              surveyScores={surveyScores}
              setSurveyScores={setSurveyScores}
              onInvestmentSaved={async () => { setConfirmedExecution(false); await loadData(); }}
              onApplyProfile={async () => {
                setConfirmedExecution(false);
                await loadData();
                setActiveTab('overview');
              }}
            />
          )}

          {activeTab === 'copilot' && <CopilotTab />}
        </main>
      </div>

      {/* Rebalance Confirmation Modal with Early Withdrawal Warnings */}
      <RebalanceConfirmModal
        key={plan?.planToken ?? 'no-plan'}
        isOpen={isRebalanceModalOpen}
        onClose={() => setIsRebalanceModalOpen(false)}
        onConfirm={handleExecuteActualRebalance}
        plan={plan}
        executing={executingRebalance}
      />

      {/* Auth Modal for Login and Registration */}
      <AuthModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
        onSuccess={loadData}
      />
    </div>
  );
}
