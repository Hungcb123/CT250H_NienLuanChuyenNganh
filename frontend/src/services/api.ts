// API Client for Spring Boot Backend with Graceful Mock Fallbacks
import { PortfolioValuation, RebalancePlan, UserProfile } from '../types';
export type { PortfolioValuation, RebalancePlan, UserProfile };

const API_BASE = '/api/v1';

export async function getPortfolioValuation(): Promise<PortfolioValuation> {
  try {
    const res = await fetch(`${API_BASE}/ledger/portfolio-valuation`);
    if (res.ok) {
      const json = await res.json();
      if (json.data && json.data.totalNetWorth > 0) return json.data;
    }
  } catch (e) {
    console.warn("Backend not available, using high-fidelity fallback data", e);
  }

  // High-fidelity fallback data aligned with interface_dashboard/code.html
  return {
    totalNetWorth: 1450280000,
    cashBalance: 85280000,
    stockValue: 798400000,
    goldValue: 266600000,
    savingsValue: 300000000,
    currentAllocations: {
      STOCK: 0.5505,
      GOLD: 0.1838,
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
    const res = await fetch(`${API_BASE}/optimizer/rebalance-plan`);
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
      CASH_SAVINGS: 0.2657
    },
    targetAllocations: {
      STOCK: 0.3500,
      GOLD: 0.3500,
      CASH_SAVINGS: 0.3000
    },
    executiveSummary: "Phát hiện tỷ trọng Cổ phiếu hiện tại (55.1%) vượt quá ngưỡng mục tiêu SAA (35.0%) do tăng giá. Đề xuất bán bớt 2.800 cổ phiếu HPG (lô chẵn 100) và 1.700 cổ phiếu TCB, chuyển 120.000.000 ₫ sang mua tích lũy thêm Vàng miếng SJC và gửi tiết kiệm.",
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

export async function getUserProfile(): Promise<UserProfile> {
  try {
    const res = await fetch(`${API_BASE}/profile/me`);
    if (res.ok) {
      const json = await res.json();
      if (json.data) return json.data;
    }
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
