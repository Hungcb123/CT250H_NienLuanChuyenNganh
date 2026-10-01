// Core TypeScript Definitions for EquiFolio Frontend

export type TabType = 'overview' | 'ledger' | 'markowitz' | 'savings' | 'survey' | 'copilot';

export interface HoldingItem {
  accountCode: string;
  ticker: string;
  assetName: string;
  assetClass: string;
  quantity: number;
  currentPrice: number;
  marketValue: number;
  allocationPercent: number;
}

export interface PortfolioValuation {
  totalNetWorth: number;
  cashBalance: number;
  stockValue: number;
  goldValue: number;
  savingsValue: number;
  currentAllocations: {
    STOCK?: number;
    GOLD?: number;
    CASH_SAVINGS?: number;
  };
  holdings: HoldingItem[];
}

export interface RebalanceAction {
  actionType: string;
  ticker: string;
  assetName: string;
  assetClass: string;
  exactQuantity: number;
  roundedQuantity: number;
  estimatedPrice: number;
  estimatedTotalMoney: number;
  note: string;
}

export interface RebalancePlan {
  driftDetected: boolean;
  maxDriftPercent: number;
  currentAllocations: Record<string, number>;
  targetAllocations: Record<string, number>;
  executiveSummary: string;
  actions: RebalanceAction[];
}

export interface UserProfile {
  id: number;
  username: string;
  email: string;
  riskScore: number;
  riskAversionLambda: number;
  riskProfile: string;
}

export interface SurveyOption {
  text: string;
  val: number;
}

export interface SurveyQuestion {
  q: string;
  desc: string;
  score: number;
  options: SurveyOption[];
}
