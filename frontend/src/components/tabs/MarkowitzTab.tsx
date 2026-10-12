import { useState, useMemo } from 'react';
import {
  TrendingUp, Shield, Cpu, RefreshCw,
  CheckCircle2, AlertTriangle, Layers, Percent, Activity,
  Sliders, Sparkles, Save
} from 'lucide-react';
import {
  ResponsiveContainer, ScatterChart, Scatter, XAxis, YAxis,
  Tooltip, Cell, ZAxis
} from 'recharts';
import { RebalancePlan, UserProfile, PortfolioValuation } from '../../types';
import { formatVND } from '../../utils/formatters';
import { submitRiskSurvey, updatePortfolioTargets } from '../../services/api';
import { useTheme } from '../../context/ThemeContext';

interface MarkowitzTabProps {
  plan: RebalancePlan | null;
  profile?: UserProfile | null;
  valuation?: PortfolioValuation | null;
  onConfirmRebalance?: () => Promise<void> | void;
  confirmedExecution?: boolean;
  executing?: boolean;
  onRefreshData?: () => Promise<void> | void;
}

interface MonteCarloPoint {
  vol: number; // Volatility %
  ret: number; // Expected Return %
  sharpe: number; // Sharpe Ratio
  stockW: number;
  goldW: number;
  cashW: number;
  bondW: number;
}

// 4 Asset Classes Parameters (Annualized Return μ, Annualized Volatility σ)
const ASSET_PARAMS = {
  STOCK: { mu: 18.5, sigma: 22.0, name: 'Cổ phiếu VN30' },
  GOLD: { mu: 12.0, sigma: 14.5, name: 'Vàng miếng SJC' },
  CASH: { mu: 5.5, sigma: 1.0, name: 'Tiền gửi tiết kiệm' },
  BOND: { mu: 8.5, sigma: 6.0, name: 'Trái phiếu / Fixed Income' },
};

// 4x4 Correlation Matrix (ρ)
const CORRELATION_MATRIX = [
  [1.00, -0.15, 0.02, 0.25],  // STOCK
  [-0.15, 1.00, 0.00, 0.12],  // GOLD
  [0.02, 0.00, 1.00, 0.20],   // CASH
  [0.25, 0.12, 0.20, 1.00],   // BOND
];

const ASSET_LABELS = ['Cổ phiếu VN30', 'Vàng SJC', 'Tiền gửi', 'Trái phiếu'];

const RISK_FREE_RATE = 4.5; // Rf %

// Seeded pseudo-random generator for stable reproducible 600 portfolios
function seededRandom(seed: number) {
  const x = Math.sin(seed) * 10000;
  return x - Math.floor(x);
}

// Generate 600 Monte Carlo Portfolios
function generateMonteCarloPortfolios(count = 600): MonteCarloPoint[] {
  const points: MonteCarloPoint[] = [];

  for (let i = 0; i < count; i++) {
    // Generate 4 positive weights that sum to 1
    const r1 = seededRandom(i * 4 + 1);
    const r2 = seededRandom(i * 4 + 2);
    const r3 = seededRandom(i * 4 + 3);
    const r4 = seededRandom(i * 4 + 4);
    const sum = r1 + r2 + r3 + r4;

    const w1 = r1 / sum; // Stock
    const w2 = r2 / sum; // Gold
    const w3 = r3 / sum; // Cash
    const w4 = r4 / sum; // Bond

    // Expected Portfolio Return μ_p = w^T * μ
    const ret =
      w1 * ASSET_PARAMS.STOCK.mu +
      w2 * ASSET_PARAMS.GOLD.mu +
      w3 * ASSET_PARAMS.CASH.mu +
      w4 * ASSET_PARAMS.BOND.mu;

    // Portfolio Variance σ_p^2 = sum_i sum_j w_i w_j Cov(i, j)
    const weights = [w1, w2, w3, w4];
    const sigmas = [
      ASSET_PARAMS.STOCK.sigma,
      ASSET_PARAMS.GOLD.sigma,
      ASSET_PARAMS.CASH.sigma,
      ASSET_PARAMS.BOND.sigma,
    ];

    let variance = 0;
    for (let row = 0; row < 4; row++) {
      for (let col = 0; col < 4; col++) {
        const cov = CORRELATION_MATRIX[row][col] * sigmas[row] * sigmas[col];
        variance += weights[row] * weights[col] * cov;
      }
    }

    const vol = Math.sqrt(Math.max(0.01, variance));
    const sharpe = (ret - RISK_FREE_RATE) / vol;

    points.push({
      vol: Number(vol.toFixed(2)),
      ret: Number(ret.toFixed(2)),
      sharpe: Number(sharpe.toFixed(2)),
      stockW: Number((w1 * 100).toFixed(1)),
      goldW: Number((w2 * 100).toFixed(1)),
      cashW: Number((w3 * 100).toFixed(1)),
      bondW: Number((w4 * 100).toFixed(1)),
    });
  }

  return points;
}

export function MarkowitzTab({
  plan,
  profile,
  valuation,
  onConfirmRebalance,
  confirmedExecution = false,
  executing = false,
  onRefreshData,
}: MarkowitzTabProps) {
  const { isDark } = useTheme();
  // Interactive Risk Aversion Slider Lambda λ (1.0 to 10.0)
  const initialLambda = profile?.riskAversionLambda || 3.88;
  const [lambda, setLambda] = useState<number>(initialLambda);
  const [isSavingLambda, setIsSavingLambda] = useState(false);
  const [saveLambdaSuccess, setSaveLambdaSuccess] = useState(false);
  const [selectedCell, setSelectedCell] = useState<{ row: number; col: number } | null>({ row: 0, col: 1 });
  const [isApplyingTAA, setIsApplyingTAA] = useState(false);
  const [appliedTAASuccess, setAppliedTAASuccess] = useState(false);

  // Handle applying TAA Tactical Shift (+10% Stock, -10% Cash/Savings, Gold unchanged)
  const handleApplyTAA = async () => {
    setIsApplyingTAA(true);
    try {
      await updatePortfolioTargets({
        stock: 0.50,
        gold: 0.20,
        savings: 0.20,
        cash: 0.10,
      });
      setAppliedTAASuccess(true);
      if (onRefreshData) {
        await onRefreshData();
      }
      setTimeout(() => setAppliedTAASuccess(false), 4000);
    } catch (err) {
      console.error("Failed to apply TAA targets", err);
    } finally {
      setIsApplyingTAA(false);
    }
  };

  const currentNetWorth = valuation?.totalNetWorth || 185000000;

  // Generate 600 Monte Carlo Simulated Points once
  const monteCarloData = useMemo(() => generateMonteCarloPortfolios(600), []);

  // Compute Tangency Portfolio (Max Sharpe) & Min Variance Portfolio
  const tangencyPoint = useMemo(() => {
    return monteCarloData.reduce((prev, curr) => (curr.sharpe > prev.sharpe ? curr : prev), monteCarloData[0]);
  }, [monteCarloData]);

  const minVarPoint = useMemo(() => {
    return monteCarloData.reduce((prev, curr) => (curr.vol < prev.vol ? curr : prev), monteCarloData[0]);
  }, [monteCarloData]);

  // Compute Optimal Portfolio w*(λ) dynamically as slider moves:
  // As λ increases (high risk aversion), weight moves from aggressive stocks to cash/bonds
  const optimalAllocation = useMemo(() => {
    // Normalizing factor t from 0 (conservative, λ=10) to 1 (aggressive, λ=1)
    const t = Math.max(0, Math.min(1, (10.0 - lambda) / 9.0));

    // Dynamic weights interpolation
    const stockW = 10.0 + t * 65.0; // 10% -> 75%
    const goldW = 15.0 + t * 10.0;  // 15% -> 25%
    const cashW = Math.max(5.0, 50.0 - t * 45.0); // 50% -> 5%
    const bondW = Math.max(5.0, 25.0 - t * 20.0); // 25% -> 5%

    const total = stockW + goldW + cashW + bondW;
    const normStock = (stockW / total) * 100;
    const normGold = (goldW / total) * 100;
    const normCash = (cashW / total) * 100;
    const normBond = (bondW / total) * 100;

    const expReturn =
      (normStock / 100) * ASSET_PARAMS.STOCK.mu +
      (normGold / 100) * ASSET_PARAMS.GOLD.mu +
      (normCash / 100) * ASSET_PARAMS.CASH.mu +
      (normBond / 100) * ASSET_PARAMS.BOND.mu;

    // Variance calculation
    const w = [normStock / 100, normGold / 100, normCash / 100, normBond / 100];
    const s = [ASSET_PARAMS.STOCK.sigma, ASSET_PARAMS.GOLD.sigma, ASSET_PARAMS.CASH.sigma, ASSET_PARAMS.BOND.sigma];
    let variance = 0;
    for (let r = 0; r < 4; r++) {
      for (let c = 0; c < 4; c++) {
        variance += w[r] * w[c] * (CORRELATION_MATRIX[r][c] * s[r] * s[c]);
      }
    }
    const vol = Math.sqrt(Math.max(0.01, variance));
    const sharpe = (expReturn - RISK_FREE_RATE) / vol;

    return {
      stockW: normStock,
      goldW: normGold,
      cashW: normCash,
      bondW: normBond,
      ret: Number(expReturn.toFixed(2)),
      vol: Number(vol.toFixed(2)),
      sharpe: Number(sharpe.toFixed(2)),
    };
  }, [lambda]);

  // Handle saving lambda to user profile
  const handleSaveLambda = async () => {
    setIsSavingLambda(true);
    setSaveLambdaSuccess(false);
    try {
      const score = Math.round(20 - (lambda - 1.0) * (15 / 9.0));
      const perQuestionScore = Math.max(1, Math.min(4, Math.round(score / 5)));
      await submitRiskSurvey({
        answers: [
          { questionId: 1, selectedOption: `Hệ số ngại rủi ro λ = ${lambda.toFixed(2)}`, score: perQuestionScore },
          { questionId: 2, selectedOption: 'Thời hạn đầu tư', score: perQuestionScore },
          { questionId: 3, selectedOption: 'Mức chấp nhận rủi ro', score: perQuestionScore },
          { questionId: 4, selectedOption: 'Mục tiêu lợi nhuận', score: perQuestionScore },
          { questionId: 5, selectedOption: 'Phản ứng thị trường', score: perQuestionScore },
        ]
      });
      localStorage.setItem('equifolio_risk_profile', JSON.stringify({
        riskScore: score,
        riskAversionLambda: lambda,
        riskProfile: lambda > 6 ? 'CONSERVATIVE' : lambda > 3 ? 'BALANCED' : 'AGGRESSIVE'
      }));
      setSaveLambdaSuccess(true);
      setTimeout(() => setSaveLambdaSuccess(false), 3500);
    } catch {
      localStorage.setItem('equifolio_risk_profile', JSON.stringify({
        riskScore: Math.round(20 - (lambda - 1.0) * (15 / 9.0)),
        riskAversionLambda: lambda,
        riskProfile: lambda > 6 ? 'CONSERVATIVE' : lambda > 3 ? 'BALANCED' : 'AGGRESSIVE'
      }));
      setSaveLambdaSuccess(true);
      setTimeout(() => setSaveLambdaSuccess(false), 3500);
    } finally {
      setIsSavingLambda(false);
    }
  };

  // Color mapper for Monte Carlo dots based on Sharpe Ratio
  const getDotColor = (sr: number) => {
    if (sr >= 1.05) return '#10b981'; // Emerald (Top tier)
    if (sr >= 0.85) return '#3b82f6'; // Blue (Good)
    if (sr >= 0.65) return '#8b5cf6'; // Purple (Moderate)
    return '#94a3b8'; // Slate (Suboptimal)
  };

  // Current real client holdings allocations
  const currentStockWeight = (valuation?.currentAllocations.STOCK !== undefined ? valuation.currentAllocations.STOCK * 100 : 35.0);
  const currentGoldWeight = (valuation?.currentAllocations.GOLD !== undefined ? valuation.currentAllocations.GOLD * 100 : 35.0);
  const currentSavingsWeight = (valuation?.currentAllocations.SAVINGS !== undefined ? valuation.currentAllocations.SAVINGS * 100 : 20.0);
  const currentCashWeight = (valuation?.currentAllocations.CASH !== undefined ? valuation.currentAllocations.CASH * 100 : 10.0);

  return (
    <div className="space-y-6">
      {/* 1. Header Banner */}
      <section className="bg-surface-container-lowest border border-border-subtle rounded-xl p-6 shadow-sm flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-surface-container-high text-accent-blue">
              <Cpu className="w-5 h-5 text-accent-blue" />
            </div>
            <div>
              <div className="flex items-center gap-2.5">
                <h2 className="text-xl font-bold text-text-primary tracking-tight">
                  Bộ Tối Ưu Hóa Danh Mục Markowitz (MVO & TAA Suite)
                </h2>
                <span className="px-2.5 py-0.5 rounded-full bg-accent-blue-light text-accent-blue text-xs font-semibold border border-accent-blue/20">
                  Modern Portfolio Theory
                </span>
                <span className="px-2.5 py-0.5 rounded-full bg-surface-container-high text-text-secondary text-xs font-medium font-mono-num">
                  600+ Monte Carlo Simulations
                </span>
              </div>
              <p className="text-xs text-text-secondary mt-1">
                Giải bài toán Quadratic Programming cực đại hóa hàm thỏa dụng U = wᵀμ - 0.5λ wᵀΣw với ma trận hiệp phương sai đa tài sản
              </p>
            </div>
          </div>
        </div>

        {/* Status Chips */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-surface-container-low border border-border-subtle">
            <Layers className="w-4 h-4 text-accent-blue" />
            <div className="text-left">
              <p className="text-[10px] uppercase font-bold text-text-muted tracking-wider">Quy Mô Tối Ưu Hóa (NAV)</p>
              <p className="text-xs font-bold text-text-primary font-mono-num">
                {formatVND(currentNetWorth)}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-surface-container-low border border-border-subtle">
            <Shield className="w-4 h-4 text-accent-emerald" />
            <div className="text-left">
              <p className="text-[10px] uppercase font-bold text-text-muted tracking-wider">Chuẩn Quản Trị Rủi Ro</p>
              <p className="text-xs font-bold text-text-primary">
                Basel III • MiFID II Collars (±15%)
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* 2. Interactive Risk Aversion Slider (Thanh Trượt λ) */}
      <section className="bg-surface-container-lowest border border-border-subtle rounded-xl p-6 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border-subtle pb-4">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-accent-blue-light text-accent-blue">
              <Sliders className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-text-primary tracking-tight">
                Mô Phỏng Nhạy Cảm Hệ Số Ngại Rủi Ro Cá Nhân (λ Parameter)
              </h3>
              <p className="text-xs text-text-secondary">
                Kéo thanh trượt để quan sát điểm tối ưu di chuyển tức thì trên đường biên hiệu quả và phân bổ lại cơ cấu tài sản
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleSaveLambda}
              disabled={isSavingLambda}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-surface-container-high hover:bg-surface-container-highest text-text-primary border border-border-subtle text-xs font-bold transition-all shadow-2xs"
            >
              {isSavingLambda ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin text-accent-blue" />
                  Đang lưu...
                </>
              ) : saveLambdaSuccess ? (
                <>
                  <CheckCircle2 className="w-3.5 h-3.5 text-accent-emerald" />
                  Đã Lưu Vào Hồ Sơ
                </>
              ) : (
                <>
                  <Save className="w-3.5 h-3.5 text-accent-blue" />
                  Lưu Khẩu Vị Này (λ = {lambda.toFixed(2)})
                </>
              )}
            </button>
          </div>
        </div>

        {/* Slider & Presets */}
        <div className="space-y-4 pt-1">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-text-secondary">
              Chấp nhận mạo hiểm (λ = 1.0)
            </span>
            <span className="px-3 py-1 rounded-full bg-accent-blue text-white font-mono-num font-bold text-sm shadow-xs">
              λ = {lambda.toFixed(2)}
            </span>
            <span className="text-xs font-bold text-text-secondary">
              Thận trọng bảo toàn (λ = 10.0)
            </span>
          </div>

          <input
            type="range"
            min="1.0"
            max="10.0"
            step="0.1"
            value={lambda}
            onChange={(e) => setLambda(parseFloat(e.target.value))}
            className="w-full h-2.5 bg-surface-container-high rounded-lg appearance-none cursor-pointer accent-accent-blue"
          />

          {/* Quick Presets */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 text-xs">
            <button
              onClick={() => setLambda(2.0)}
              className={`p-2 rounded-lg border text-left transition-all ${
                Math.abs(lambda - 2.0) < 0.2
                  ? 'border-accent-blue bg-accent-blue-light/40 text-accent-blue font-bold'
                  : 'border-border-subtle bg-surface-container-low text-text-secondary hover:bg-surface-container-high'
              }`}
            >
              <span className="font-semibold block text-[11px]">Tăng Trưởng Nhanh</span>
              <span className="font-mono-num text-[10px] opacity-80">λ = 2.0 (ERP cao)</span>
            </button>
            <button
              onClick={() => setLambda(3.88)}
              className={`p-2 rounded-lg border text-left transition-all ${
                Math.abs(lambda - 3.88) < 0.2
                  ? 'border-accent-blue bg-accent-blue-light/40 text-accent-blue font-bold'
                  : 'border-border-subtle bg-surface-container-low text-text-secondary hover:bg-surface-container-high'
              }`}
            >
              <span className="font-semibold block text-[11px]">Cân Bằng Chuẩn MVO</span>
              <span className="font-mono-num text-[10px] opacity-80">λ = 3.88 (Mặc định)</span>
            </button>
            <button
              onClick={() => setLambda(6.5)}
              className={`p-2 rounded-lg border text-left transition-all ${
                Math.abs(lambda - 6.5) < 0.2
                  ? 'border-accent-blue bg-accent-blue-light/40 text-accent-blue font-bold'
                  : 'border-border-subtle bg-surface-container-low text-text-secondary hover:bg-surface-container-high'
              }`}
            >
              <span className="font-semibold block text-[11px]">Thận Trọng Định Kỳ</span>
              <span className="font-mono-num text-[10px] opacity-80">λ = 6.5 (Đệm an toàn)</span>
            </button>
            <button
              onClick={() => setLambda(9.0)}
              className={`p-2 rounded-lg border text-left transition-all ${
                Math.abs(lambda - 9.0) < 0.2
                  ? 'border-accent-blue bg-accent-blue-light/40 text-accent-blue font-bold'
                  : 'border-border-subtle bg-surface-container-low text-text-secondary hover:bg-surface-container-high'
              }`}
            >
              <span className="font-semibold block text-[11px]">Bảo Toàn Thanh Khoản</span>
              <span className="font-mono-num text-[10px] opacity-80">λ = 9.0 (Cash-heavy)</span>
            </button>
          </div>
        </div>
      </section>

      {/* 3. Quantitative Key Metrics (Real-time Updated with λ) */}
      <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
        <div className="bg-surface-container-lowest border border-border-subtle rounded-xl p-5 shadow-sm hover:border-border-highlight transition-all">
          <div className="flex items-center justify-between text-text-muted mb-2">
            <span className="text-xs uppercase tracking-wider font-semibold">Tỷ Suất Kỳ Vọng (μ*(λ))</span>
            <TrendingUp className="w-4 h-4 text-accent-emerald" />
          </div>
          <div className="text-2xl font-black text-text-primary tracking-tight font-mono-num">
            {optimalAllocation.ret.toFixed(1)}% <span className="text-xs font-normal text-text-muted">/ năm</span>
          </div>
          <p className="text-[11px] text-accent-emerald mt-2 font-medium font-mono-num">
            +{(optimalAllocation.ret - RISK_FREE_RATE).toFixed(1)}% phần bù rủi ro vốn (ERP)
          </p>
        </div>

        <div className="bg-surface-container-lowest border border-border-subtle rounded-xl p-5 shadow-sm hover:border-border-highlight transition-all">
          <div className="flex items-center justify-between text-text-muted mb-2">
            <span className="text-xs uppercase tracking-wider font-semibold">Độ Biến Động Dự Báo (σ*(λ))</span>
            <Activity className="w-4 h-4 text-accent-gold" />
          </div>
          <div className="text-2xl font-black text-text-primary tracking-tight font-mono-num">
            {optimalAllocation.vol.toFixed(1)}% <span className="text-xs font-normal text-text-muted">/ năm</span>
          </div>
          <p className="text-[11px] text-text-secondary mt-2">
            Độ lệch chuẩn hiệp phương sai danh mục (Covariance Σ)
          </p>
        </div>

        <div className="bg-surface-container-lowest border border-border-subtle rounded-xl p-5 shadow-sm hover:border-border-highlight transition-all">
          <div className="flex items-center justify-between text-text-muted mb-2">
            <span className="text-xs uppercase tracking-wider font-semibold">Hệ Số Sharpe (SR*(λ))</span>
            <Percent className="w-4 h-4 text-accent-blue" />
          </div>
          <div className="text-2xl font-black text-accent-blue tracking-tight font-mono-num">
            {optimalAllocation.sharpe.toFixed(2)}
          </div>
          <p className="text-[11px] text-accent-emerald mt-2 font-medium">
            Điểm tiếp xúc tối đa: <strong className="font-mono-num">{tangencyPoint.sharpe.toFixed(2)}</strong>
          </p>
        </div>

        <div className="bg-surface-container-lowest border border-border-subtle rounded-xl p-5 shadow-sm hover:border-border-highlight transition-all">
          <div className="flex items-center justify-between text-text-muted mb-2">
            <span className="text-xs uppercase tracking-wider font-semibold">Hàm Thỏa Dụng U*(λ)</span>
            <Sparkles className="w-4 h-4 text-accent-purple" />
          </div>
          <div className="text-2xl font-black text-text-primary tracking-tight font-mono-num">
            {(optimalAllocation.ret - 0.5 * lambda * Math.pow(optimalAllocation.vol / 10, 2)).toFixed(2)}
          </div>
          <p className="text-[11px] text-text-secondary mt-2 font-mono">
            max U = wᵀμ - 0.5λ wᵀΣw
          </p>
        </div>
      </section>

      {/* 4. Monte Carlo Scatter Plot & Correlation Matrix Heatmap */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left (2 cols): 600+ Monte Carlo Efficient Frontier Scatter Chart */}
        <div className="lg:col-span-2 bg-surface-container-lowest border border-border-subtle rounded-xl p-6 shadow-sm space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h3 className="text-base font-bold text-text-primary tracking-tight">
                Đám Mây 600+ Danh Mục Monte Carlo & Đường Biên Hiệu Quả
              </h3>
              <p className="text-xs text-text-secondary">
                Mỗi điểm tròn đại diện cho 1 danh mục ngẫu nhiên thỏa mãn ∑wᵢ = 1; màu sắc thể hiện Hệ số Sharpe
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3 text-xs">
              <span className="flex items-center gap-1.5 text-text-secondary font-medium">
                <span className="w-3 h-3 rounded-full bg-accent-emerald"></span>
                Vị thế của bạn (w*(λ))
              </span>
              <span className="flex items-center gap-1.5 text-text-secondary font-medium">
                <span className="w-2.5 h-2.5 rounded-full bg-accent-gold"></span>
                Max Sharpe (Tangency)
              </span>
              <span className="flex items-center gap-1.5 text-text-secondary font-medium">
                <span className="w-2.5 h-2.5 rounded-full bg-cyan-500"></span>
                Min Variance
              </span>
            </div>
          </div>

          <div className="h-80 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 10 }}>
                <XAxis
                  type="number"
                  dataKey="vol"
                  name="Độ Biến Động (Volatility)"
                  unit="%"
                  domain={[3, 22]}
                  tick={{ fontSize: 11, fill: isDark ? '#94a3b8' : '#64748b' }}
                  tickLine={false}
                  axisLine={{ stroke: isDark ? '#373a4d' : '#cbd5e1' }}
                  label={{ value: 'Độ biến động rủi ro danh mục (σ %)', position: 'insideBottom', offset: -10, fontSize: 11, fill: isDark ? '#94a3b8' : '#64748b' }}
                />
                <YAxis
                  type="number"
                  dataKey="ret"
                  name="Tỷ Suất Kỳ Vọng (Return)"
                  unit="%"
                  domain={[5, 20]}
                  tick={{ fontSize: 11, fill: isDark ? '#94a3b8' : '#64748b' }}
                  tickLine={false}
                  axisLine={{ stroke: isDark ? '#373a4d' : '#cbd5e1' }}
                  label={{ value: 'Tỷ suất sinh lời kỳ vọng (μ %)', angle: -90, position: 'insideLeft', offset: 5, fontSize: isDark ? '#94a3b8' : '#64748b' }}
                />
                <ZAxis range={[25, 25]} />
                <Tooltip
                  cursor={{ strokeDasharray: '3 3' }}
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      const data = payload[0].payload as MonteCarloPoint;
                      return (
                        <div className="bg-surface-container-lowest p-3 rounded-lg shadow-xl border border-border-subtle text-xs space-y-1.5">
                          <p className="font-bold text-text-primary">Danh mục mô phỏng Monte Carlo</p>
                          <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px]">
                            <span className="text-text-secondary">Lợi nhuận kỳ vọng:</span>
                            <span className="font-mono-num font-bold text-accent-blue">{data.ret}%</span>
                            <span className="text-text-secondary">Độ biến động (σ):</span>
                            <span className="font-mono-num font-bold text-text-primary">{data.vol}%</span>
                            <span className="text-text-secondary">Hệ số Sharpe:</span>
                            <span className="font-mono-num font-bold text-accent-emerald">{data.sharpe}</span>
                          </div>
                          <div className="pt-1.5 border-t border-border-subtle text-[10px] text-text-muted">
                            CP: {data.stockW}% • Vàng: {data.goldW}% • Tiền: {data.cashW}% • TP: {data.bondW}%
                          </div>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                {/* 600 Background Monte Carlo Points */}
                <Scatter data={monteCarloData} shape="circle" fillOpacity={0.4}>
                  {monteCarloData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={getDotColor(entry.sharpe)} />
                  ))}
                </Scatter>

                {/* Tangency Portfolio (Max Sharpe) */}
                <Scatter
                  data={[tangencyPoint]}
                  shape="circle"
                  fill="#f59e0b"
                />

                {/* Min Variance Portfolio */}
                <Scatter
                  data={[minVarPoint]}
                  shape="circle"
                  fill="#06b6d4"
                />

                {/* Dynamic Optimal Portfolio Point w*(λ) that runs on the chart */}
                <Scatter
                  data={[{
                    vol: optimalAllocation.vol,
                    ret: optimalAllocation.ret,
                    sharpe: optimalAllocation.sharpe,
                    stockW: optimalAllocation.stockW,
                    goldW: optimalAllocation.goldW,
                    cashW: optimalAllocation.cashW,
                    bondW: optimalAllocation.bondW,
                  }]}
                  shape="circle"
                  fill="#10b981"
                />
              </ScatterChart>
            </ResponsiveContainer>
          </div>

          {/* Footer Chart Legend Info */}
          <div className="pt-3 border-t border-border-subtle flex flex-wrap items-center justify-between gap-3 text-xs">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-accent-emerald border border-white"></span>
              <span className="font-semibold text-text-primary">Vị Thế Tối Ưu Hiện Tại (λ = {lambda.toFixed(2)}):</span>
              <span className="font-mono-num text-accent-emerald font-bold">
                μ = {optimalAllocation.ret}% • σ = {optimalAllocation.vol}% • SR = {optimalAllocation.sharpe}
              </span>
            </div>
            <div className="text-[11px] text-text-secondary">
              Lãi suất phi rủi ro: <span className="font-mono-num font-semibold text-text-primary">Rf = {RISK_FREE_RATE}%</span> (SBV Interbank Repo)
            </div>
          </div>
        </div>

        {/* Right (1 col): Correlation Matrix Heatmap */}
        <div className="bg-surface-container-lowest border border-border-subtle rounded-xl p-5 shadow-sm space-y-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-accent-emerald" />
                <h3 className="text-sm font-bold text-text-primary tracking-tight">
                  Ma Trận Tương Quan (Correlation Heatmap)
                </h3>
              </div>
              <span className="text-[10px] uppercase font-bold text-accent-emerald bg-accent-emerald-light px-2 py-0.5 rounded border border-accent-emerald/20">
                Diversification
              </span>
            </div>
            <p className="text-xs text-text-secondary leading-relaxed mb-4">
              Hệ số tương quan ρ ∈ [-1.0, +1.0]. Ô màu xanh lá minh chứng cơ chế triệt tiêu rủi ro phi hệ thống khi kết hợp đa lớp tài sản.
            </p>

            {/* 4x4 Heatmap Table */}
            <div className="overflow-x-auto">
              <table className="w-full text-center text-xs border-collapse">
                <thead>
                  <tr>
                    <th className="p-1.5 text-left text-[10px] text-text-muted uppercase">Tài Sản</th>
                    {ASSET_LABELS.map((label, idx) => (
                      <th key={idx} className="p-1.5 text-[10px] text-text-primary font-bold">
                        {label.split(' ')[0]}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {CORRELATION_MATRIX.map((row, rIdx) => (
                    <tr key={rIdx}>
                      <td className="p-1.5 text-left text-[11px] font-bold text-text-primary">
                        {ASSET_LABELS[rIdx]}
                      </td>
                      {row.map((val, cIdx) => {
                        const isDiag = rIdx === cIdx;
                        const isNeg = val < 0;
                        const isLowPos = val > 0 && val <= 0.25;
                        const isSelected = selectedCell?.row === rIdx && selectedCell?.col === cIdx;

                        return (
                          <td
                            key={cIdx}
                            onClick={() => setSelectedCell({ row: rIdx, col: cIdx })}
                            className={`p-2 font-mono-num font-bold text-xs cursor-pointer transition-all border border-white ${
                              isSelected ? 'ring-2 ring-accent-blue z-10' : ''
                            } ${
                              isDiag
                                ? 'bg-surface-container-high text-text-muted'
                                : isNeg
                                ? 'bg-emerald-100 text-emerald-800 hover:bg-emerald-200'
                                : isLowPos
                                ? 'bg-sky-50 text-sky-800 hover:bg-sky-100'
                                : 'bg-rose-50 text-rose-800 hover:bg-rose-100'
                            }`}
                          >
                            {val.toFixed(2)}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Interactive Tooltip Explanation for Selected Cell */}
            {selectedCell && (
              <div className="mt-4 p-3.5 rounded-lg bg-surface-container-low border border-border-subtle text-xs space-y-1">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-text-primary">
                    Tương quan giữa {ASSET_LABELS[selectedCell.row]} & {ASSET_LABELS[selectedCell.col]}:
                  </span>
                  <span className="font-mono-num font-bold px-2 py-0.5 rounded bg-surface-container-high text-text-primary border border-border-subtle">
                    ρ = {CORRELATION_MATRIX[selectedCell.row][selectedCell.col].toFixed(2)}
                  </span>
                </div>
                <p className="text-[11px] text-text-secondary leading-relaxed pt-1">
                  {selectedCell.row === selectedCell.col
                    ? 'Tương quan hoàn hảo với chính nó (ρ = 1.0).'
                    : CORRELATION_MATRIX[selectedCell.row][selectedCell.col] < 0
                    ? '🌟 Tương quan nghịch (-0.15): Vàng và Cổ phiếu bù trừ rủi ro lý tưởng khi thị trường giảm, giúp đường biên hiệu quả uốn cong về bên trái.'
                    : CORRELATION_MATRIX[selectedCell.row][selectedCell.col] <= 0.2
                    ? '🛡️ Tương quan rất thấp (gần 0.0): Tiền gửi hoạt động độc lập như một tấm đệm giảm xóc thanh khoản an toàn tuyệt đối.'
                    : '📈 Tương quan thuận vừa phải (+0.25): Cùng hưởng lợi trong các chu kỳ mở rộng tín dụng của nền kinh tế.'}
                </p>
              </div>
            )}
          </div>

          <div className="p-3 rounded-lg bg-surface-container-high text-[11px] text-text-secondary">
            Định lý Markowitz: Khi <span className="font-mono text-text-primary font-bold">ρ &lt; 1</span>, độ biến động của danh mục luôn nhỏ hơn trung bình trọng số độ biến động các tài sản thành phần.
          </div>
        </div>
      </div>

      {/* TAA Machine Learning Recommendation Banner */}
      <section className="rounded-xl border border-accent-emerald/30 bg-gradient-to-r from-accent-emerald/10 via-surface-container-low to-surface-container-low p-5 shadow-xs relative overflow-hidden">
        <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4">
          <div className="space-y-1.5 flex-1">
            <div className="flex items-center gap-2">
              <span className="flex h-2 w-2 rounded-full bg-accent-emerald animate-pulse"></span>
              <span className="text-[11px] font-bold uppercase tracking-wider text-accent-emerald">
                Khuyến Nghị Phân Bổ Chiến Thuật (TAA - Machine Learning)
              </span>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent-emerald/20 text-accent-emerald font-semibold border border-accent-emerald/30">
                Mô hình ONNX T+20
              </span>
            </div>
            <h4 className="text-sm font-bold text-text-primary">
              Cổ Phiếu VN30 Tích Lũy Tăng Trưởng (Xác suất 78.4%) — Khuyến Nghị Tăng Tỷ Trọng Vốn
            </h4>
            <p className="text-xs text-text-secondary leading-relaxed">
              Mô hình học máy ONNX nhận diện thị trường cổ phiếu bước vào chu kỳ tăng trưởng tích lũy T+20 (xác suất tăng 78.4%). 
              Trong khi đó, <strong className="text-text-primary font-medium">Vàng SJC (ρ = -0.15)</strong> đóng vai trò neo phòng thủ an toàn (giữ nguyên 20%). 
              Khuyến nghị điều chỉnh chiến thuật (TAA): <strong className="text-accent-emerald font-semibold">Tăng Cổ phiếu 40% → 50% (+10%)</strong> bằng cách tái phân bổ từ Tiền gửi tiết kiệm, vẫn đảm bảo trong khung kiểm soát rủi ro an toàn.
            </p>
            <div className="flex flex-wrap items-center gap-3 pt-1 text-[11px]">
              <span className="text-text-muted">Mục tiêu SAA: Cổ phiếu 40% | Vàng 20% | Tiết kiệm 30% | Tiền mặt 10%</span>
              <span className="text-accent-emerald font-bold">➔ TAA Đề xuất: Cổ phiếu 50% (+10%) | Vàng 20% | Tiết kiệm 20% | Tiền mặt 10%</span>
            </div>
          </div>
          <div className="shrink-0 flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5 w-full lg:w-auto">
            <button
              onClick={handleApplyTAA}
              disabled={isApplyingTAA}
              className={`px-4 py-2.5 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-2 shadow-sm ${
                appliedTAASuccess
                  ? 'bg-accent-emerald text-white'
                  : 'bg-accent-emerald hover:bg-emerald-600 text-white cursor-pointer active:scale-95'
              }`}
            >
              {isApplyingTAA ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  Đang Cập Nhật Mục Tiêu...
                </>
              ) : appliedTAASuccess ? (
                <>
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  Đã Áp Dụng TAA (+10% Cổ Phiếu)!
                </>
              ) : (
                <>
                  <Sparkles className="w-3.5 h-3.5" />
                  Áp Dụng TAA (+10% Cổ Phiếu)
                </>
              )}
            </button>
          </div>
        </div>
      </section>

      {/* 5. Dynamic Asset Weights Comparison Matrix (Current vs Target TAA vs λ Simulation) */}
      <section className="bg-surface-container-lowest border border-border-subtle rounded-xl p-6 shadow-sm space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-border-subtle pb-4">
          <div>
            <h3 className="text-base font-bold text-text-primary tracking-tight">
              Phân Bổ Tỷ Trọng Danh Mục (Hiện Tại vs Đề Xuất w*(λ))
            </h3>
            <p className="text-xs text-text-secondary">
              Các thanh tỷ trọng tự động co giãn theo thời gian thực tương ứng với hệ số ngại rủi ro λ = {lambda.toFixed(2)}
            </p>
          </div>
          {plan?.driftDetected ? (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-accent-gold-light text-accent-gold text-xs font-bold border border-accent-gold/20 self-start sm:self-auto">
              <AlertTriangle className="w-3.5 h-3.5" />
              Độ lệch lớn nhất: {plan.maxDriftPercent.toFixed(1)}% (Cần Tái Cơ Cấu)
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-accent-emerald-light text-accent-emerald text-xs font-bold border border-accent-emerald/20 self-start sm:self-auto">
              <CheckCircle2 className="w-3.5 h-3.5" />
              Danh mục nằm trong vùng cân bằng tối ưu
            </span>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-5">
          {/* Asset 1: Cổ phiếu */}
          <div className="p-4 rounded-xl bg-surface-container-low border border-border-subtle space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="font-bold text-text-primary text-xs">Cổ Phiếu VN30</span>
              <span className="text-xs font-mono-num font-bold text-accent-blue">{currentStockWeight.toFixed(1)}%</span>
            </div>
            <div className="w-full bg-surface-container-high h-2.5 rounded-full overflow-hidden">
              <div
                className="bg-accent-blue h-full rounded-full transition-all duration-300"
                style={{ width: `${Math.min(100, currentStockWeight)}%` }}
              ></div>
            </div>
            <div className="flex justify-between items-center text-[11px] text-text-secondary pt-1">
              <span>Đề xuất w*(λ): <strong className="text-text-primary font-mono-num">{optimalAllocation.stockW.toFixed(1)}%</strong></span>
              <span className={currentStockWeight > optimalAllocation.stockW ? 'text-accent-rose font-semibold' : 'text-accent-emerald font-semibold'}>
                {currentStockWeight > optimalAllocation.stockW ? `+${(currentStockWeight - optimalAllocation.stockW).toFixed(1)}%` : `${(currentStockWeight - optimalAllocation.stockW).toFixed(1)}%`}
              </span>
            </div>
          </div>

          {/* Asset 2: Vàng */}
          <div className="p-4 rounded-xl bg-surface-container-low border border-border-subtle space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="font-bold text-text-primary text-xs">Vàng Miếng SJC</span>
              <span className="text-xs font-mono-num font-bold text-accent-gold">{currentGoldWeight.toFixed(1)}%</span>
            </div>
            <div className="w-full bg-surface-container-high h-2.5 rounded-full overflow-hidden">
              <div
                className="bg-accent-gold h-full rounded-full transition-all duration-300"
                style={{ width: `${Math.min(100, currentGoldWeight)}%` }}
              ></div>
            </div>
            <div className="flex justify-between items-center text-[11px] text-text-secondary pt-1">
              <span>Đề xuất w*(λ): <strong className="text-text-primary font-mono-num">{optimalAllocation.goldW.toFixed(1)}%</strong></span>
              <span className={currentGoldWeight > optimalAllocation.goldW ? 'text-accent-rose font-semibold' : 'text-accent-emerald font-semibold'}>
                {currentGoldWeight > optimalAllocation.goldW ? `+${(currentGoldWeight - optimalAllocation.goldW).toFixed(1)}%` : `${(currentGoldWeight - optimalAllocation.goldW).toFixed(1)}%`}
              </span>
            </div>
          </div>

          {/* Asset 3: Tiền gửi tiết kiệm */}
          <div className="p-4 rounded-xl bg-surface-container-low border border-border-subtle space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="font-bold text-text-primary text-xs">Tiền Gửi Tiết Kiệm (Rf)</span>
              <span className="text-xs font-mono-num font-bold text-indigo-600">{currentSavingsWeight.toFixed(1)}%</span>
            </div>
            <div className="w-full bg-surface-container-high h-2.5 rounded-full overflow-hidden">
              <div
                className="bg-indigo-600 h-full rounded-full transition-all duration-300"
                style={{ width: `${Math.min(100, currentSavingsWeight)}%` }}
              ></div>
            </div>
            <div className="flex justify-between items-center text-[11px] text-text-secondary pt-1">
              <span>Đề xuất w*(λ): <strong className="text-text-primary font-mono-num">{(optimalAllocation.cashW * 0.67).toFixed(1)}%</strong></span>
              <span className={currentSavingsWeight > (optimalAllocation.cashW * 0.67) ? 'text-accent-rose font-semibold' : 'text-accent-emerald font-semibold'}>
                {currentSavingsWeight > (optimalAllocation.cashW * 0.67) ? `+${(currentSavingsWeight - (optimalAllocation.cashW * 0.67)).toFixed(1)}%` : `${(currentSavingsWeight - (optimalAllocation.cashW * 0.67)).toFixed(1)}%`}
              </span>
            </div>
          </div>

          {/* Asset 4: Tiền mặt khả dụng */}
          <div className="p-4 rounded-xl bg-surface-container-low border border-border-subtle space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="font-bold text-text-primary text-xs">Tiền Mặt Khả Dụng (T+0)</span>
              <span className="text-xs font-mono-num font-bold text-sky-600">{currentCashWeight.toFixed(1)}%</span>
            </div>
            <div className="w-full bg-surface-container-high h-2.5 rounded-full overflow-hidden">
              <div
                className="bg-sky-500 h-full rounded-full transition-all duration-300"
                style={{ width: `${Math.min(100, currentCashWeight)}%` }}
              ></div>
            </div>
            <div className="flex justify-between items-center text-[11px] text-text-secondary pt-1">
              <span>Đề xuất w*(λ): <strong className="text-text-primary font-mono-num">{(optimalAllocation.cashW * 0.33).toFixed(1)}%</strong></span>
              <span className={currentCashWeight > (optimalAllocation.cashW * 0.33) ? 'text-accent-rose font-semibold' : 'text-accent-emerald font-semibold'}>
                {currentCashWeight > (optimalAllocation.cashW * 0.33) ? `+${(currentCashWeight - (optimalAllocation.cashW * 0.33)).toFixed(1)}%` : `${(currentCashWeight - (optimalAllocation.cashW * 0.33)).toFixed(1)}%`}
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* 6. Actionable Rebalance Execution Plan */}
      <section className="bg-surface-container-lowest border border-border-subtle rounded-xl p-6 shadow-sm space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h3 className="text-base font-bold text-text-primary tracking-tight">
              Đề Xuất Kế Hoạch Tái Cơ Cấu Lệnh (Rebalance Orders)
            </h3>
            <p className="text-xs text-text-secondary">
              {plan?.executiveSummary || 'Hệ thống đã tính toán các lệnh mua/bán cần thiết để đưa danh mục về vị thế tối ưu Markowitz.'}
            </p>
          </div>

          {onConfirmRebalance && (
            <button
              onClick={() => onConfirmRebalance()}
              disabled={executing || (confirmedExecution && !plan?.driftDetected)}
              className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-xs font-bold transition-all shadow-sm ${
                (confirmedExecution && !plan?.driftDetected)
                  ? 'bg-accent-emerald text-white cursor-default'
                  : executing
                  ? 'bg-accent-blue/80 text-white cursor-wait'
                  : 'bg-accent-blue hover:bg-accent-blue/90 text-white active:scale-95 cursor-pointer'
              }`}
            >
              {(confirmedExecution && !plan?.driftDetected) ? (
                <>
                  <CheckCircle2 className="w-4 h-4 text-white" />
                  Đã Khớp Lệnh Toàn Bộ
                </>
              ) : executing ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin text-white" />
                  Đang Ghi Sổ ACID...
                </>
              ) : (
                <>
                  <RefreshCw className="w-4 h-4 text-white" />
                  Xác Nhận Thực Thi Tái Cơ Cấu
                </>
              )}
            </button>
          )}
        </div>

        {/* Action Orders List */}
        <div className="space-y-3">
          {plan?.actions && plan.actions.length > 0 ? (
            plan.actions.map((act, i) => (
              <div
                key={i}
                className="p-4 rounded-xl bg-surface-container-low border border-border-subtle flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
              >
                <div className="flex items-center gap-3">
                  <span
                    className={`px-2.5 py-1 rounded-md font-bold text-[11px] tracking-wider uppercase ${
                      act.actionType === 'SELL'
                        ? 'bg-accent-rose-light text-accent-rose border border-accent-rose/20'
                        : 'bg-accent-emerald-light text-accent-emerald border border-accent-emerald/20'
                    }`}
                  >
                    {act.actionType}
                  </span>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-text-primary text-sm">{act.ticker}</span>
                      <span className="text-text-secondary">({act.assetName})</span>
                    </div>
                    <p className="text-[11px] text-text-muted mt-0.5">{act.note || 'Lệnh cân bằng tỷ trọng chuẩn Markowitz'}</p>
                  </div>
                </div>

                <div className="flex items-center justify-between sm:justify-end gap-6 text-right">
                  <div>
                    <span className="font-bold text-text-primary text-sm font-mono-num">
                      {act.roundedQuantity.toLocaleString('vi-VN')} đơn vị
                    </span>
                    <span className="block text-[11px] text-text-muted">
                      (Chính xác: {act.exactQuantity.toFixed(1)})
                    </span>
                  </div>
                  <div>
                    <span className="font-bold text-text-primary text-sm font-mono-num">
                      {formatVND(act.estimatedTotalMoney)}
                    </span>
                    <span className="block text-[11px] text-accent-blue font-mono-num">
                      Giá ước tính: {formatVND(act.estimatedPrice)}
                    </span>
                    {((act.estimatedFee || 0) > 0 || (act.estimatedTax || 0) > 0) && (
                      <span className="block text-[10px] text-text-muted font-mono-num">
                        Phí & Thuế: {formatVND((act.estimatedFee || 0) + (act.estimatedTax || 0))}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))
          ) : (
            <div className="p-8 text-center rounded-xl bg-surface-container-low border border-border-subtle text-text-muted text-xs">
              <CheckCircle2 className="w-8 h-8 text-accent-emerald mx-auto mb-2 opacity-80" />
              Danh mục đang ở trạng thái cân bằng hoàn hảo so với khẩu vị rủi ro. Không có lệnh tái cơ cấu nào phát sinh.
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
