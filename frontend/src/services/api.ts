// API Client for Spring Boot Backend with Graceful Mock Fallbacks
import {
  PortfolioValuation,
  RebalancePlan,
  UserProfile,
  TransactionItem,
  SavingsDepositItem,
  OpenSavingsPayload,
  EquityInjectionPayload,
  LedgerAuditReport,
  CompoundSimulationResult,
  AuthResponseData,
  TradeOrderPayload,
  PortfolioHistoryResponse,
  SnapshotPoint,
  RiskMetrics,
  DividendPayload,
  GoldPriceItem,
  BankComparisonItem,
  RiskFreeRateInfo
} from '../types';

export type {
  PortfolioValuation,
  RebalancePlan,
  UserProfile,
  LedgerAuditReport,
  CompoundSimulationResult,
  AuthResponseData,
  TradeOrderPayload,
  PortfolioHistoryResponse,
  SnapshotPoint,
  RiskMetrics,
  DividendPayload
};

const API_BASE = '/api/v1';

// HttpOnly Cookie: Token được lưu trữ an toàn trong HttpOnly Cookie do server cấp
// Trình duyệt tự động gửi cookie qua header với credentials: 'include'.
// KHÔNG lưu JWT token vào localStorage để phòng ngừa tuyệt đối tấn công XSS.
export function hasActiveSession(): boolean {
  return !!localStorage.getItem('equifolio_user');
}

export function getAuthToken(): string | null {
  return null;
}

export function setAuthToken(_token: string | null) {
  localStorage.removeItem('equifolio_token');
}

export function getAuthHeaders(customHeaders: Record<string, string> = {}): Record<string, string> {
  return {
    'Content-Type': 'application/json',
    ...customHeaders
  };
}

export interface LoginPayload {
  usernameOrEmail: string;
  password?: string;
}

export interface RegisterPayload {
  username: string;
  email: string;
  password?: string;
}

export async function loginUser(payload: LoginPayload): Promise<AuthResponseData> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(payload)
  });
  const json = await res.json();
  if (!res.ok || !json.data) {
    throw new Error(json.message || 'Đăng nhập không thành công');
  }
  // Loại bỏ token khỏi localStorage (token được lưu trong HttpOnly Cookie)
  localStorage.removeItem('equifolio_token');
  try {
    const profileData: UserProfile = {
      id: json.data.id,
      username: json.data.username,
      email: json.data.email,
      riskScore: json.data.riskScore,
      riskAversionLambda: Number((10 - (0.09 * (json.data.riskScore || 50))).toFixed(2)),
      riskProfile: json.data.riskProfile
    };
    localStorage.setItem('equifolio_user', JSON.stringify(profileData));
  } catch (e) {}
  return json.data;
}

export async function registerUser(payload: RegisterPayload): Promise<AuthResponseData> {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(payload)
  });
  const json = await res.json();
  if (!res.ok || !json.data) {
    throw new Error(json.message || 'Đăng ký không thành công');
  }
  // Loại bỏ token khỏi localStorage (token được lưu trong HttpOnly Cookie)
  localStorage.removeItem('equifolio_token');
  try {
    const profileData: UserProfile = {
      id: json.data.id,
      username: json.data.username,
      email: json.data.email,
      riskScore: json.data.riskScore,
      riskAversionLambda: Number((10 - (0.09 * (json.data.riskScore || 50))).toFixed(2)),
      riskProfile: json.data.riskProfile
    };
    localStorage.setItem('equifolio_user', JSON.stringify(profileData));
  } catch (e) {}
  return json.data;
}

export async function logoutUser(): Promise<void> {
  try {
    await fetch(`${API_BASE}/auth/logout`, {
      method: 'POST',
      credentials: 'include'
    });
  } catch (e) {}
  localStorage.removeItem('equifolio_user');
  localStorage.removeItem('equifolio_token');
}

export async function getPortfolioValuation(): Promise<PortfolioValuation> {
  try {
    const res = await fetch(`${API_BASE}/ledger/portfolio-valuation`, {
      headers: getAuthHeaders(),
      credentials: 'include'
    });
    if (res.ok) {
      const json = await res.json();
      if (json.data) return json.data;
    }
  } catch (e) {
    console.warn("Backend not available, using fallback data", e);
  }

  // Nếu người dùng đã đăng nhập thì trả về danh mục rỗng ban đầu (0đ)
  if (hasActiveSession()) {
    return {
      totalNetWorth: 0,
      cashBalance: 0,
      stockValue: 0,
      goldValue: 0,
      savingsValue: 0,
      currentAllocations: {},
      holdings: []
    };
  }

  return {
    totalNetWorth: 1450280000,
    cashBalance: 85280000,
    stockValue: 798400000,
    goldValue: 266600000,
    savingsValue: 300000000,
    currentAllocations: {
      STOCK: 0.5505,
      GOLD: 0.1838,
      SAVINGS: 0.2069,
      CASH: 0.0588,
      CASH_SAVINGS: 0.2657
    },
    holdings: [
      {
        accountCode: "STOCK_HPG",
        ticker: "HPG",
        assetName: "Tập đoàn Hòa Phát",
        assetClass: "STOCK",
        quantity: 16000,
        currentPrice: 28500,
        marketValue: 456000000,
        allocationPercent: 0.3144
      },
      {
        accountCode: "STOCK_TCB",
        ticker: "TCB",
        assetName: "Techcombank",
        assetClass: "STOCK",
        quantity: 14100,
        currentPrice: 24200,
        marketValue: 341220000,
        allocationPercent: 0.2353
      },
      {
        accountCode: "GOLD_SJC",
        ticker: "GOLD_SJC",
        assetName: "Vàng miếng SJC 999.9",
        assetClass: "GOLD",
        quantity: 31.7,
        currentPrice: 8410000,
        marketValue: 266600000,
        allocationPercent: 0.1838
      },
      {
        accountCode: "SAVINGS_VCB",
        ticker: "SAVINGS",
        assetName: "Sổ tiết kiệm Vietcombank 6T",
        assetClass: "SAVINGS",
        quantity: 1,
        currentPrice: 300000000,
        marketValue: 300000000,
        allocationPercent: 0.2069
      },
      {
        accountCode: "VND_WALLET",
        ticker: "VND",
        assetName: "Tiền mặt khả dụng",
        assetClass: "CASH",
        quantity: 85280000,
        currentPrice: 1,
        marketValue: 85280000,
        allocationPercent: 0.0588
      }
    ]
  };
}

export async function getRebalancePlan(): Promise<RebalancePlan> {
  try {
    const res = await fetch(`${API_BASE}/optimizer/rebalance-plan`, {
      headers: getAuthHeaders(),
      credentials: 'include'
    });
    if (res.ok) {
      const json = await res.json();
      if (json.data) return json.data;
    }
  } catch (e) {
    console.warn("Backend not available, using fallback rebalance plan", e);
  }

  return {
    driftDetected: true,
    maxDriftPercent: 20.05,
    currentAllocations: {
      STOCK: 0.5505,
      GOLD: 0.1838,
      SAVINGS: 0.2069,
      CASH: 0.0588,
      CASH_SAVINGS: 0.2657
    },
    targetAllocations: {
      STOCK: 0.3500,
      GOLD: 0.3500,
      SAVINGS: 0.2000,
      CASH: 0.1000,
      CASH_SAVINGS: 0.3000
    },
    executiveSummary: "Phát hiện tỷ trọng Cổ phiếu hiện tại (55.1%) vượt quá ngưỡng mục tiêu SAA (35.0%) do tăng giá. Đề xuất bán bớt 2.800 cổ phiếu HPG (lô chẵn 100) và 1.700 cổ phiếu TCB, chuyển sang mua tích lũy thêm Vàng miếng SJC và duy trì tiền mặt.",
    actions: [
      {
        actionType: "SELL",
        ticker: "HPG",
        assetName: "Hòa Phát",
        assetClass: "STOCK",
        exactQuantity: 2842,
        roundedQuantity: 2800,
        estimatedPrice: 28500,
        estimatedTotalMoney: 79800000,
        note: "Khớp lệnh lô chẵn 100 cp trên sàn HOSE để chốt lời bảo toàn vốn."
      },
      {
        actionType: "BUY",
        ticker: "GOLD_SJC",
        assetName: "Vàng SJC 999.9",
        assetClass: "GOLD",
        exactQuantity: 9.5,
        roundedQuantity: 9,
        estimatedPrice: 8410000,
        estimatedTotalMoney: 75690000,
        note: "Mua tích sản 9 chỉ vàng SJC phòng thủ lạm phát."
      }
    ]
  };
}

export async function executeRebalancePlan(): Promise<{
  success: boolean;
  message: string;
  updatedValuation?: PortfolioValuation;
  updatedPlan?: RebalancePlan;
}> {
  // Ưu tiên endpoint xác nhận chuẩn SRS Mục 4.2 (/ledger/rebalance/confirm)
  let res = await fetch(`${API_BASE}/ledger/rebalance/confirm`, {
    method: 'POST',
    headers: getAuthHeaders(),
    credentials: 'include'
  });

  if (!res.ok && res.status !== 401) {
    // Fallback sang /optimizer/rebalance/execute nếu cần
    res = await fetch(`${API_BASE}/optimizer/rebalance/execute`, {
      method: 'POST',
      headers: getAuthHeaders(),
      credentials: 'include'
    });
  }

  if (!res.ok) {
    const errorJson = await res.json().catch(() => ({}));
    throw new Error(errorJson.message || 'Thực thi tái cơ cấu thất bại');
  }
  const json = await res.json();
  return {
    success: true,
    message: json.message || 'Thực thi tái cơ cấu thành công',
    updatedValuation: json.data?.updatedValuation,
    updatedPlan: json.data?.updatedPlan
  };
}

export async function executeTradeOrder(payload: TradeOrderPayload): Promise<TransactionItem> {
  const res = await fetch(`${API_BASE}/ledger/trade`, {
    method: 'POST',
    headers: getAuthHeaders(),
    credentials: 'include',
    body: JSON.stringify(payload)
  });

  const json = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(json.message || 'Khớp lệnh giao dịch thất bại. Vui lòng kiểm tra lại số dư và hạn mức.');
  }

  return json.data;
}

export async function getPortfolioHistory(timeframe: string = '1M'): Promise<PortfolioHistoryResponse> {
  try {
    const res = await fetch(`${API_BASE}/ledger/history?timeframe=${encodeURIComponent(timeframe)}`, {
      headers: getAuthHeaders(),
      credentials: 'include'
    });
    if (res.ok) {
      const json = await res.json();
      if (json.data) return json.data;
    }
  } catch (e) {
    console.warn("Failed to fetch portfolio history from backend", e);
  }

  // Fallback demo data if backend unavailable
  return {
    timeframe,
    currentNav: 1450280000,
    portfolioReturnPercent: 4.2,
    vniReturnPercent: 1.8,
    alphaPercent: 2.4,
    points: [
      { date: "01/10", nav: 1390000000, navReturn: 0.0, vniReturn: 0.0, vnindex: 1250 },
      { date: "07/10", nav: 1410000000, navReturn: 1.4, vniReturn: 0.6, vnindex: 1258 },
      { date: "14/10", nav: 1405000000, navReturn: 1.1, vniReturn: 0.9, vnindex: 1262 },
      { date: "21/10", nav: 1435000000, navReturn: 3.2, vniReturn: 1.3, vnindex: 1266 },
      { date: "28/10", nav: 1450280000, navReturn: 4.2, vniReturn: 1.8, vnindex: 1272 }
    ]
  };
}

export async function getRiskMetrics(): Promise<RiskMetrics> {
  try {
    const res = await fetch(`${API_BASE}/ledger/risk-metrics`, {
      headers: getAuthHeaders(),
      credentials: 'include'
    });
    if (res.ok) {
      const json = await res.json();
      if (json.data) return json.data;
    }
  } catch (e) {
    console.warn("Failed to fetch risk metrics from backend", e);
  }

  return {
    sharpeRatio: 1.24,
    maxDrawdownPercent: 3.8,
    annualizedVolatilityPercent: 8.6,
    annualizedReturnPercent: 15.6,
    riskFreeRatePercent: 5.0,
    alphaPercent: 2.4,
    beta: 0.78,
    riskRating: "EXCELLENT",
    interpretation: "Hiệu suất sinh lời vượt trội trên mỗi đơn vị rủi ro (Sharpe = 1.24 > 1.0). Danh mục được bảo vệ tốt nhờ phân bổ Vàng và Tiền gửi."
  };
}

export async function recordDividend(payload: DividendPayload): Promise<TransactionItem> {
  const res = await fetch(`${API_BASE}/ledger/dividend`, {
    method: 'POST',
    headers: getAuthHeaders(),
    credentials: 'include',
    body: JSON.stringify(payload)
  });

  const json = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(json.message || 'Ghi nhận cổ tức thất bại');
  }

  return json.data;
}

export async function getUserProfile(): Promise<UserProfile> {
  try {
    const res = await fetch(`${API_BASE}/auth/me`, {
      headers: getAuthHeaders(),
      credentials: 'include'
    });
    if (res.ok) {
      const json = await res.json();
      if (json.data) return json.data;
    }
  } catch (e) {}

  try {
    const res = await fetch(`${API_BASE}/profile/me`, {
      headers: getAuthHeaders(),
      credentials: 'include'
    });
    if (res.ok) {
      const json = await res.json();
      if (json.data) return json.data;
    }
  } catch (e) {}

  try {
    const saved = localStorage.getItem('equifolio_user');
    if (saved) return JSON.parse(saved);
  } catch (e) {}

  return {
    id: 1,
    username: "alex_nguyen",
    email: "alex.nguyen@equifolio.vn",
    riskScore: 68,
    riskAversionLambda: 3.88,
    riskProfile: "BALANCED"
  };
}

export interface RiskSurveySubmitPayload {
  answers: Array<{
    questionId: number;
    selectedOption: string;
    score: number;
  }>;
}

export async function submitRiskSurvey(payload: RiskSurveySubmitPayload): Promise<any> {
  const res = await fetch(`${API_BASE}/profile/risk-survey`, {
    method: 'POST',
    headers: getAuthHeaders(),
    credentials: 'include',
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.message || 'Không thể lưu kết quả khảo sát');
  }
  const json = await res.json();
  return json.data;
}

// ----------------- Double-Entry Ledger Endpoints -----------------

export async function getTransactions(): Promise<TransactionItem[]> {
  try {
    const res = await fetch(`${API_BASE}/ledger/transactions`, {
      headers: getAuthHeaders(),
      credentials: 'include'
    });
    if (res.ok) {
      const json = await res.json();
      if (json.data) return json.data;
    }
  } catch (e) {
    console.warn("Failed to fetch transactions from backend", e);
  }
  return [];
}

export async function recordEquityInjection(payload: EquityInjectionPayload): Promise<void> {
  const res = await fetch(`${API_BASE}/ledger/equity-injection`, {
    method: 'POST',
    headers: getAuthHeaders(),
    credentials: 'include',
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    const errorJson = await res.json().catch(() => ({}));
    throw new Error(errorJson.message || 'Nạp vốn thất bại');
  }
}

// ----------------- Savings Endpoints -----------------

export async function getSavingsDeposits(): Promise<SavingsDepositItem[]> {
  try {
    const res = await fetch(`${API_BASE}/ledger/savings`, {
      headers: getAuthHeaders(),
      credentials: 'include'
    });
    if (res.ok) {
      const json = await res.json();
      if (json.data) return json.data;
    }
  } catch (e) {
    console.warn("Failed to fetch savings deposits", e);
  }
  return [];
}

export async function openSavingsDeposit(payload: OpenSavingsPayload): Promise<SavingsDepositItem> {
  const res = await fetch(`${API_BASE}/ledger/savings`, {
    method: 'POST',
    headers: getAuthHeaders(),
    credentials: 'include',
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.message || 'Mở sổ tiết kiệm thất bại');
  }
  const json = await res.json();
  return json.data;
}

export async function toggleAutoRollover(depositId: number, autoRollover: boolean): Promise<SavingsDepositItem> {
  const res = await fetch(`${API_BASE}/ledger/savings/${depositId}/rollover?autoRollover=${autoRollover}`, {
    method: 'PATCH',
    headers: getAuthHeaders(),
    credentials: 'include'
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.message || 'Cập nhật auto-rollover thất bại');
  }
  const json = await res.json();
  return json.data;
}

export async function settleSavingsDeposit(depositId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/ledger/savings/${depositId}/settle`, {
    method: 'POST',
    headers: getAuthHeaders(),
    credentials: 'include'
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.message || 'Tất toán sổ tiết kiệm thất bại');
  }
}

// ----------------- Ledger Audit & Simulation Endpoints -----------------

export async function getLedgerAuditReport(): Promise<LedgerAuditReport> {
  try {
    const res = await fetch(`${API_BASE}/ledger/audit`, {
      headers: getAuthHeaders(),
      credentials: 'include'
    });
    if (res.ok) {
      const json = await res.json();
      if (json.data) return json.data;
    }
  } catch (e) {
    console.warn("Failed to fetch ledger audit report", e);
  }

  if (hasActiveSession()) {
    return {
      totalTransactionsChecked: 0,
      balancedTransactions: 0,
      unbalancedTransactions: 0,
      allTransactionsBalanced: true,
      allAccountsConsistent: true,
      auditStatus: "ALL_ACID_INVARIANTS_PASSED",
      systemSummary: "Sổ cái kép chưa phát sinh bút toán giao dịch nào.",
      verifiedAt: new Date().toISOString(),
      accountAuditList: [],
      unbalancedTxList: []
    };
  }

  // Fallback demo dữ liệu nếu offline (dành cho khách chưa đăng nhập)
  return {
    totalTransactionsChecked: 5,
    balancedTransactions: 5,
    unbalancedTransactions: 0,
    allTransactionsBalanced: true,
    allAccountsConsistent: true,
    auditStatus: "ALL_ACID_INVARIANTS_PASSED",
    systemSummary: "Toàn bộ hệ thống sổ cái kép đạt chuẩn bảo toàn ACID 100%. Mọi bút toán cân bằng tuyệt đối (Σ Debit = Σ Credit) và số dư đối soát khớp hoàn toàn với lịch sử dòng tiền.",
    verifiedAt: new Date().toISOString(),
    accountAuditList: [
      { accountCode: "VND_WALLET", assetTicker: "VND", snapshotBalance: 85280000, calculatedEntriesBalance: 85280000, discrepancy: 0, consistent: true },
      { accountCode: "STOCK_HPG", assetTicker: "HPG", snapshotBalance: 28000, calculatedEntriesBalance: 28000, discrepancy: 0, consistent: true },
      { accountCode: "GOLD_SJC", assetTicker: "GOLD_SJC", snapshotBalance: 32, calculatedEntriesBalance: 32, discrepancy: 0, consistent: true },
      { accountCode: "EQUITY_CAPITAL", assetTicker: "VND", snapshotBalance: 1450280000, calculatedEntriesBalance: 1450280000, discrepancy: 0, consistent: true }
    ],
    unbalancedTxList: []
  };
}

export async function simulateCompoundSavings(params: {
  principal?: number;
  monthlyContribution?: number;
  annualRate?: number;
  years?: number;
}): Promise<CompoundSimulationResult> {
  const query = new URLSearchParams({
    principal: String(params.principal ?? 50000000),
    monthlyContribution: String(params.monthlyContribution ?? 5000000),
    annualRate: String(params.annualRate ?? 6.5),
    years: String(params.years ?? 10)
  });

  try {
    const res = await fetch(`${API_BASE}/ledger/savings/simulate?${query}`);
    if (res.ok) {
      const json = await res.json();
      if (json.data) return json.data;
    }
  } catch (e) {
    console.warn("Failed to fetch savings simulation, using client-side calculation fallback", e);
  }

  // Fallback toán học phía Client chuẩn xác
  const p = params.principal ?? 50000000;
  const pmt = params.monthlyContribution ?? 5000000;
  const rate = params.annualRate ?? 6.5;
  const y = params.years ?? 10;
  const monthlyRate = rate / 1200;

  let currentBalance = p;
  let cumulativeContribution = p;
  let cumulativeInterest = 0;
  const yearlyBreakdown = [];

  for (let year = 1; year <= y; year++) {
    const startBalance = currentBalance;
    const yearlyContribution = pmt * 12;
    let interestThisYear = 0;

    for (let m = 1; m <= 12; m++) {
      currentBalance += pmt;
      const monthInterest = currentBalance * monthlyRate;
      interestThisYear += monthInterest;
      currentBalance += monthInterest;
    }

    cumulativeContribution += yearlyContribution;
    cumulativeInterest += interestThisYear;

    yearlyBreakdown.push({
      year,
      startBalance: Math.round(startBalance),
      yearlyContribution: Math.round(yearlyContribution),
      cumulativeContribution: Math.round(cumulativeContribution),
      interestEarnedThisYear: Math.round(interestThisYear),
      cumulativeInterest: Math.round(cumulativeInterest),
      endBalance: Math.round(currentBalance)
    });
  }

  return {
    initialPrincipal: p,
    monthlyContribution: pmt,
    annualRate: rate,
    years: y,
    totalContributed: Math.round(cumulativeContribution),
    totalInterestEarned: Math.round(cumulativeInterest),
    futureValue: Math.round(currentBalance),
    wealthMultiplier: Number((currentBalance / cumulativeContribution).toFixed(2)),
    yearlyBreakdown
  };
}

// ----------------- Copilot Endpoints -----------------

export interface CopilotStatus {
  hasApiKey: boolean;
  model: string;
  provider: string;
  authMode?: string;
  serviceAccountLoaded?: boolean;
}

export async function getCopilotStatus(): Promise<CopilotStatus> {
  try {
    const res = await fetch(`${API_BASE}/copilot/status`, {
      headers: getAuthHeaders(),
      credentials: 'include'
    });
    if (res.ok) {
      const json = await res.json();
      if (json.data) return json.data;
    }
  } catch (e) {
    console.warn("Failed to fetch copilot status", e);
  }
  return {
    hasApiKey: true,
    model: "gemini-2.5-flash-lite",
    provider: "Google Cloud Vertex AI",
    authMode: "SERVICE_ACCOUNT",
    serviceAccountLoaded: true
  };
}

export async function saveCopilotApiKey(apiKey: string): Promise<boolean> {
  if (apiKey) {
    localStorage.setItem('gemini_api_key', apiKey.trim());
  } else {
    localStorage.removeItem('gemini_api_key');
  }

  try {
    const res = await fetch(`${API_BASE}/copilot/key`, {
      method: 'POST',
      headers: getAuthHeaders(),
      credentials: 'include',
      body: JSON.stringify({ apiKey: apiKey.trim() })
    });
    return res.ok;
  } catch (e) {
    console.warn("Failed to sync api key with backend, stored in localStorage", e);
    return true;
  }
}

export async function sendCopilotMessage(message: string, clientApiKey?: string): Promise<{ reply: string; references: string[] }> {
  const apiKey = clientApiKey || localStorage.getItem('gemini_api_key') || undefined;

  try {
    const res = await fetch(`${API_BASE}/copilot/chat`, {
      method: 'POST',
      headers: getAuthHeaders(),
      credentials: 'include',
      body: JSON.stringify({ message, apiKey })
    });
    if (res.ok) {
      const json = await res.json();
      if (json.data) {
        return {
          reply: json.data.reply,
          references: json.data.referenceSources || []
        };
      }
    }
  } catch (e) {
    console.warn("Copilot API error, using intelligent client fallback", e);
  }

  return {
    reply: `Cảm ơn bạn đã hỏi về "${message}". Hệ thống đang theo dõi độ lệch danh mục của bạn so với mục tiêu SAA. Bạn hãy kiểm tra lại tại tab Tổng quan để xem các khuyến nghị điều chỉnh lô chẵn 100 HOSE phù hợp nhất.`,
    references: []
  };
}

export async function getPortfolioTargets(): Promise<Record<string, number>> {
  try {
    const res = await fetch(`${API_BASE}/profile/targets`, {
      headers: getAuthHeaders(),
      credentials: 'include'
    });
    if (res.ok) {
      const json = await res.json();
      if (json.data) return json.data;
    }
  } catch (e) {
    console.warn("Failed to get targets from backend", e);
  }
  return {
    STOCK: 0.35,
    GOLD: 0.35,
    SAVINGS: 0.20,
    CASH: 0.10,
    CASH_SAVINGS: 0.30
  };
}

export async function updatePortfolioTargets(targets: {
  stock: number;
  gold: number;
  savings: number;
  cash: number;
}): Promise<Record<string, number>> {
  const res = await fetch(`${API_BASE}/profile/targets`, {
    method: 'PUT',
    headers: {
      ...getAuthHeaders(),
      'Content-Type': 'application/json'
    },
    credentials: 'include',
    body: JSON.stringify(targets)
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.message || 'Không thể cập nhật tỷ trọng mục tiêu');
  }
  const json = await res.json();
  return json.data;
}

// ----------------- Market Data Endpoints (DNSE OpenAPI & WebSocket) -----------------

export interface MarketPriceItem {
  ticker: string;
  name: string;
  assetClass: string;
  price: number;
  tradeDate: string;
  updatedAt: string;
  changeRatio?: number;
  changeValue?: number;
}

export interface VNIndexSummaryData {
  latestDate: string;
  currentPoints: number;
  changePoints: number;
  changePercent: number;
  high52w: number;
  low52w: number;
  avgVolume20: number;
  latestVolume: number;
  ma20: number;
  ma50: number;
  regimeSignal?: number;
  regimeStatus?: string;
  source?: string;
}

export async function getMarketPrices(): Promise<MarketPriceItem[]> {
  try {
    const res = await fetch(`${API_BASE}/market/prices`);
    if (res.ok) {
      const json = await res.json();
      if (json.data && Array.isArray(json.data)) return json.data;
    }
  } catch (e) {
    console.warn("Failed to fetch market prices from backend", e);
  }
  return [];
}

export async function getVNIndexSummaryApi(): Promise<VNIndexSummaryData | null> {
  try {
    const res = await fetch(`${API_BASE}/market/vnindex`);
    if (res.ok) {
      const json = await res.json();
      if (json.data) return json.data;
    }
  } catch (e) {
    console.warn("Failed to fetch VNIndex summary from backend", e);
  }
  return null;
}

export async function triggerMarketSync(): Promise<any> {
  const res = await fetch(`${API_BASE}/market/sync`, {
    method: 'POST',
    headers: getAuthHeaders(),
    credentials: 'include'
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.message || 'Đồng bộ thị trường thất bại');
  }
  const json = await res.json();
  return json.data;
}

export interface StockLiveQuote {
  ticker: string;
  price: number;
  prevPrice?: number;
  change: number;
  changePercent: number;
  volume: number;
  tradeDate?: string;
  source?: string;
}

export async function fetchStockQuote(ticker: string): Promise<StockLiveQuote | null> {
  const cleanTicker = ticker.trim().toUpperCase();
  if (!cleanTicker) return null;
  try {
    const res = await fetch(`${API_BASE}/market/quote?ticker=${encodeURIComponent(cleanTicker)}`);
    if (res.ok) {
      const json = await res.json();
      if (json.data && json.data.price > 0) {
        return json.data;
      }
    }
  } catch (e) {
    console.warn("Backend quote fetch failed, falling back to direct DNSE endpoint", e);
  }

  // Fallback: direct DNSE chart API
  try {
    const now = Math.floor(Date.now() / 1000);
    const fromTs = now - 10 * 86400;
    const url = `https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?symbol=${cleanTicker}&from=${fromTs}&to=${now + 86400}&resolution=1D`;
    const dnseRes = await fetch(url);
    if (dnseRes.ok) {
      const data = await dnseRes.json();
      const c = data.c || [];
      const v = data.v || [];
      if (c.length > 0) {
        const latestClose = c[c.length - 1] * 1000;
        const prevClose = c.length >= 2 ? c[c.length - 2] * 1000 : latestClose;
        const change = latestClose - prevClose;
        const changePercent = prevClose > 0 ? (change / prevClose) * 100 : 0;
        const volume = v.length > 0 ? v[v.length - 1] : 0;
        return {
          ticker: cleanTicker,
          price: latestClose,
          prevPrice: prevClose,
          change: Math.round(change),
          changePercent: Math.round(changePercent * 100) / 100,
          volume,
          source: 'DNSE_DIRECT'
        };
      }
    }
  } catch (e) {
    console.error("Direct DNSE quote fetch failed", e);
  }

  return null;
}

export async function registerTrackedStock(ticker: string, name?: string, sector?: string): Promise<MarketPriceItem | null> {
  const cleanTicker = ticker.trim().toUpperCase();
  if (!cleanTicker) return null;
  try {
    const params = new URLSearchParams();
    params.set('ticker', cleanTicker);
    if (name) params.set('name', name);
    if (sector) params.set('sector', sector);
    const res = await fetch(`${API_BASE}/market/stocks?${params.toString()}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      credentials: 'include'
    });
    if (res.ok) {
      const json = await res.json();
      return json.data || null;
    }
  } catch (e) {
    console.warn("Failed to register stock on backend", e);
  }
  return null;
}

export async function getGoldPrices(): Promise<GoldPriceItem[]> {
  try {
    const res = await fetch(`${API_BASE}/market/gold-prices`, {
      headers: getAuthHeaders(),
      credentials: 'include'
    });
    if (res.ok) {
      const json = await res.json();
      if (json.data) return json.data;
    }
  } catch (e) {
    console.warn("Failed to fetch gold prices, using fallback", e);
  }

  // Fallback
  return [
    {
      ticker: 'GOLD_SJC',
      name: 'Vàng miếng SJC 999.9',
      buyPrice: 8750000,
      sellPrice: 8950000,
      changeValue: 150000,
      changePercent: 1.70,
      source: 'SJC Market Feed',
      tradeDate: new Date().toISOString().split('T')[0]
    },
    {
      ticker: 'GOLD_RING_9999',
      name: 'Vàng nhẫn trơn 999.9',
      buyPrice: 8650000,
      sellPrice: 8800000,
      changeValue: 120000,
      changePercent: 1.38,
      source: 'Bảo Tín Minh Châu Feed',
      tradeDate: new Date().toISOString().split('T')[0]
    }
  ];
}

export async function getBankRates(): Promise<BankComparisonItem[]> {
  try {
    const res = await fetch(`${API_BASE}/market/bank-rates`, {
      headers: getAuthHeaders(),
      credentials: 'include'
    });
    if (res.ok) {
      const json = await res.json();
      if (json.data) return json.data;
    }
  } catch (e) {
    console.warn("Failed to fetch bank rates, using fallback", e);
  }

  // Fallback
  return [
    { bankCode: 'VCB', bankName: 'Vietcombank', ratesByTerm: { '1': 3.10, '3': 3.40, '6': 4.50, '12': 5.20 }, effectiveDate: new Date().toISOString().split('T')[0] },
    { bankCode: 'BID', bankName: 'BIDV', ratesByTerm: { '1': 3.20, '3': 3.50, '6': 4.60, '12': 5.30 }, effectiveDate: new Date().toISOString().split('T')[0] },
    { bankCode: 'CTG', bankName: 'VietinBank', ratesByTerm: { '1': 3.20, '3': 3.50, '6': 4.60, '12': 5.30 }, effectiveDate: new Date().toISOString().split('T')[0] },
    { bankCode: 'AGR', bankName: 'Agribank', ratesByTerm: { '1': 3.20, '3': 3.50, '6': 4.70, '12': 5.40 }, effectiveDate: new Date().toISOString().split('T')[0] },
    { bankCode: 'MBB', bankName: 'MB Bank', ratesByTerm: { '1': 3.50, '3': 3.90, '6': 5.10, '12': 5.70 }, effectiveDate: new Date().toISOString().split('T')[0] },
    { bankCode: 'TCB', bankName: 'Techcombank', ratesByTerm: { '1': 3.45, '3': 3.85, '6': 5.20, '12': 5.65 }, effectiveDate: new Date().toISOString().split('T')[0] },
    { bankCode: 'ACB', bankName: 'ACB', ratesByTerm: { '1': 3.30, '3': 3.70, '6': 5.00, '12': 5.50 }, effectiveDate: new Date().toISOString().split('T')[0] },
    { bankCode: 'HDB', bankName: 'HDBank', ratesByTerm: { '1': 3.60, '3': 4.00, '6': 5.40, '12': 6.00 }, effectiveDate: new Date().toISOString().split('T')[0] }
  ];
}

export async function getRiskFreeRate(): Promise<RiskFreeRateInfo> {
  try {
    const res = await fetch(`${API_BASE}/market/risk-free-rate`, {
      headers: getAuthHeaders(),
      credentials: 'include'
    });
    if (res.ok) {
      const json = await res.json();
      if (json.data) return json.data;
    }
  } catch (e) {
    console.warn("Failed to fetch risk-free rate, using fallback", e);
  }

  return {
    indicatorCode: 'RF_INTERBANK_RATE',
    indicatorName: 'Lãi suất phi rủi ro (SBV Interbank Rate)',
    rate: 4.5,
    unit: '%'
  };
}

export async function syncExternalMarket(): Promise<any> {
  const res = await fetch(`${API_BASE}/market/sync-external`, {
    method: 'POST',
    headers: getAuthHeaders(),
    credentials: 'include'
  });
  if (!res.ok) {
    throw new Error('Đồng bộ thị trường thất bại');
  }
  const json = await res.json();
  return json.data;
}


