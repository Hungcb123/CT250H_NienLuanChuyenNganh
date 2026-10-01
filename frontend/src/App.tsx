import { useState, useEffect } from 'react';
import { TabType, PortfolioValuation, RebalancePlan, UserProfile } from './types';
import { getPortfolioValuation, getRebalancePlan, getUserProfile } from './services/api';
import { Sidebar } from './components/layout/Sidebar';
import { Header } from './components/layout/Header';
import { OverviewTab } from './components/tabs/OverviewTab';
import { LedgerTab } from './components/tabs/LedgerTab';
import { MarkowitzTab } from './components/tabs/MarkowitzTab';
import { SavingsTab } from './components/tabs/SavingsTab';
import { SurveyTab } from './components/tabs/SurveyTab';
import { CopilotTab } from './components/tabs/CopilotTab';

export default function App() {
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [valuation, setValuation] = useState<PortfolioValuation | null>(null);
  const [plan, setPlan] = useState<RebalancePlan | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [confirmedExecution, setConfirmedExecution] = useState(false);

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
    } catch (e) {
      console.error("Failed to load portfolio data", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleConfirmRebalance = () => {
    setConfirmedExecution(true);
    setTimeout(() => {
      alert("Hệ thống Sổ cái kép đã ghi nhận bút toán tái cơ cấu! Trạng thái danh mục đã được cân bằng lại.");
    }, 300);
  };

  return (
    <div className="min-h-screen bg-surface flex text-text-primary">
      {/* 1. Global Navigation Sidebar */}
      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} />

      {/* 2. Main Content Wrapper */}
      <div className="ml-72 flex-1 flex flex-col min-h-screen">
        <Header
          valuation={valuation}
          profile={profile}
          loading={loading}
          onRefresh={loadData}
        />

        <main className="p-8 space-y-6 flex-1">
          {activeTab === 'overview' && (
            <OverviewTab
              valuation={valuation}
              plan={plan}
              profile={profile}
              confirmedExecution={confirmedExecution}
              onConfirmRebalance={handleConfirmRebalance}
            />
          )}

          {activeTab === 'ledger' && <LedgerTab />}

          {activeTab === 'markowitz' && <MarkowitzTab plan={plan} />}

          {activeTab === 'savings' && <SavingsTab />}

          {activeTab === 'survey' && (
            <SurveyTab
              surveyScores={surveyScores}
              setSurveyScores={setSurveyScores}
            />
          )}

          {activeTab === 'copilot' && <CopilotTab />}
        </main>
      </div>
    </div>
  );
}
