import { useState, useEffect } from 'react';
import { TabType, PortfolioValuation, RebalancePlan, UserProfile } from './types';
import { getPortfolioValuation, getRebalancePlan, getUserProfile, executeRebalancePlan } from './services/api';
import { Sidebar } from './components/layout/Sidebar';
import { Header } from './components/layout/Header';
import { OverviewTab } from './components/tabs/OverviewTab';
import { MarketTab } from './components/tabs/MarketTab';
import { LedgerTab } from './components/tabs/LedgerTab';
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
      const res = await executeRebalancePlan();
      setConfirmedExecution(true);
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
      }
    } finally {
      setExecutingRebalance(false);
    }
  };

  const activeUserProfile = authUser || profile;

  return (
    <div className="min-h-screen bg-surface flex text-text-primary">
      {/* 1. Global Navigation Sidebar */}
      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} />

      {/* 2. Main Content Wrapper */}
      <div className="ml-72 flex-1 flex flex-col min-h-screen">
        <Header
          valuation={valuation}
          profile={activeUserProfile}
          loading={loading}
          onRefresh={loadData}
          onOpenAuth={() => setIsAuthModalOpen(true)}
        />

        <main className="p-8 space-y-6 flex-1">
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
              valuation={valuation}
              onTradeSuccess={loadData}
              onNavigateTab={(tab) => setActiveTab(tab as TabType)}
            />
          )}

          {activeTab === 'ledger' && <LedgerTab onRefresh={loadData} />}

          {activeTab === 'markowitz' && (
            <MarkowitzTab
              plan={plan}
              profile={activeUserProfile}
              valuation={valuation}
              onConfirmRebalance={handleOpenRebalanceModal}
              confirmedExecution={confirmedExecution}
              executing={executingRebalance}
              onRefreshData={loadData}
            />
          )}

          {activeTab === 'taa' && (
            <TaaTab
              plan={plan}
              profile={activeUserProfile}
              valuation={valuation}
              onRefreshData={loadData}
              onConfirmRebalance={handleOpenRebalanceModal}
              executing={executingRebalance}
            />
          )}

          {activeTab === 'savings' && <SavingsTab onRefresh={loadData} />}

          {activeTab === 'survey' && (
            <SurveyTab
              surveyScores={surveyScores}
              setSurveyScores={setSurveyScores}
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
