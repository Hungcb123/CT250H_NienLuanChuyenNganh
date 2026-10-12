// Core TypeScript Definitions for EquiFolio Frontend

export type TabType = 'overview' | 'market' | 'ledger' | 'markowitz' | 'taa' | 'savings' | 'survey' | 'copilot';

export interface HoldingItem {
  accountCode: string;
  ticker: string;
  assetName: string;
  assetClass: string;
  quantity: number;
  currentPrice: number;
  marketValue: number;
  allocationPercent: number;
  costPrice?: number;
  totalCostBasis?: number;
  unrealizedPnL?: number;
  unrealizedPnLPercent?: number;
}

export interface PortfolioValuation {
  totalNetWorth: number;
  cashBalance: number;
  stockValue: number;
  goldValue: number;
  savingsValue: number;
  totalCostBasis?: number;
  totalUnrealizedPnL?: number;
  totalPnLPercent?: number;
  totalRealizedPnL?: number;
  currentAllocations: {
    STOCK?: number;
    GOLD?: number;
    SAVINGS?: number;
    CASH?: number;
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
  estimatedFee?: number;
  estimatedTax?: number;
  netMoney?: number;
  note: string;
}

export interface RebalancePlan {
  driftDetected: boolean;
  maxDriftPercent: number;
  currentAllocations: Record<string, number>;
  targetAllocations: Record<string, number>;
  executiveSummary: string;
  actions: RebalanceAction[];
  totalEstimatedSell?: number;
  totalEstimatedBuy?: number;
  totalEstimatedFees?: number;
  totalEstimatedTax?: number;
  netCashImpact?: number;
}

export interface SnapshotPoint {
  date: string;
  nav: number;
  stockValue?: number;
  goldValue?: number;
  savingsValue?: number;
  cashValue?: number;
  navReturn: number;
  vniReturn: number;
  vnindex: number;
}

export interface PortfolioHistoryResponse {
  timeframe: string;
  currentNav: number;
  portfolioReturnPercent: number;
  vniReturnPercent: number;
  alphaPercent: number;
  points: SnapshotPoint[];
}

export interface RiskMetrics {
  sharpeRatio: number;
  maxDrawdownPercent: number;
  annualizedVolatilityPercent: number;
  annualizedReturnPercent: number;
  riskFreeRatePercent: number;
  alphaPercent: number;
  beta: number;
  riskRating: string;
  interpretation: string;
}

export interface DividendPayload {
  ticker: string;
  dividendType: 'CASH' | 'STOCK';
  amountPerShare?: number;
  totalAmount: number;
  taxPercent?: number;
  notes?: string;
}

export interface UserProfile {
  id: number;
  username: string;
  email: string;
  riskScore: number;
  riskAversionLambda: number;
  riskProfile: string;
}

export interface AuthResponseData {
  token: string;
  tokenType: string;
  id: number;
  username: string;
  email: string;
  riskScore: number;
  riskProfile: string;
  message?: string;
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

export interface EntryItem {
  id: number;
  accountId?: number;
  accountCode: string;
  assetTicker: string;
  assetName: string;
  amount: number;
  entryType: 'DEBIT' | 'CREDIT';
}

export interface TransactionItem {
  id: number;
  transactionCode: string;
  type: string;
  status: string;
  description: string;
  createdAt: string;
  entries: EntryItem[];
  totalAmount: number;
  acidBalanced: boolean;
}

export interface SavingsDepositItem {
  id: number;
  bankName: string;
  principalAmount: number;
  interestRate: number;
  termMonths: number;
  startDate: string;
  maturityDate: string;
  autoRollover: boolean;
  accruedInterest: number;
  daysElapsed: number;
  totalDays: number;
  progressPercent: number;
  status: string;
  createdAt: string;
}

export interface OpenSavingsPayload {
  bankName: string;
  principalAmount: number;
  interestRate: number;
  termMonths: number;
  autoRollover?: boolean;
}

export interface EquityInjectionPayload {
  ticker: string;
  amount: number;
  entryPrice?: number;
  description?: string;
}

export interface TradeOrderPayload {
  ticker: string;
  actionType: 'BUY' | 'SELL';
  quantity: number;
  price: number;
  notes?: string;
}

export interface CopilotMessage {
  role: 'user' | 'assistant';
  content: string;
  time: string;
  references?: string[];
}

export interface AccountAuditItem {
  accountCode: string;
  assetTicker: string;
  snapshotBalance: number;
  calculatedEntriesBalance: number;
  discrepancy: number;
  consistent: boolean;
}

export interface UnbalancedTxItem {
  transactionCode: string;
  description: string;
  totalDebit: number;
  totalCredit: number;
  imbalance: number;
}

export interface LedgerAuditReport {
  totalTransactionsChecked: number;
  balancedTransactions: number;
  unbalancedTransactions: number;
  allTransactionsBalanced: boolean;
  allAccountsConsistent: boolean;
  auditStatus: string;
  systemSummary: string;
  verifiedAt: string;
  accountAuditList: AccountAuditItem[];
  unbalancedTxList: UnbalancedTxItem[];
}

export interface YearlyGrowthItem {
  year: number;
  startBalance: number;
  yearlyContribution: number;
  cumulativeContribution: number;
  interestEarnedThisYear: number;
  cumulativeInterest: number;
  endBalance: number;
}

export interface CompoundSimulationResult {
  initialPrincipal: number;
  monthlyContribution: number;
  annualRate: number;
  years: number;
  totalContributed: number;
  totalInterestEarned: number;
  futureValue: number;
  wealthMultiplier: number;
  yearlyBreakdown: YearlyGrowthItem[];
}

