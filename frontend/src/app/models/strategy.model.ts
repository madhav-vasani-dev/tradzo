export interface MonthlyReturn {
  month: string;       // e.g. 'Jan 2024'
  returnPct: number;   // e.g. 4.2
}

export interface YearlyReturn {
  year: string;        // e.g. '2024'
  returnPct: number;
}

export interface EquityPoint {
  date: string;        // ISO date string
  value: number;       // cumulative portfolio value
}

export interface StrategyPerformance {
  cagr: number;
  sharpeRatio: number;
  maxDrawdown: number;
  winRate: number;
  totalTrades: number;
  avgTradeReturn: number;
  avgTradeDurationMinutes: number;
  profitFactor: number;
  calmarRatio: number;
  expectancy: number;
  backtestStartDate: string;
  backtestEndDate: string;
  monthlyReturns: MonthlyReturn[];
  yearlyReturns: YearlyReturn[];
  equityCurve: EquityPoint[];
}

export type StrategyCategory = 'Options' | 'Futures' | 'Equity' | 'Index';
export type RiskLevel = 'Low' | 'Medium' | 'High';

export interface Strategy {
  id: string;
  name: string;
  description: string;
  category: StrategyCategory;
  instrumentType: string;
  riskLevel: RiskLevel;
  isVisible: boolean;
  minimumAmount: number;
  tags: string[];
  performance: StrategyPerformance;
  createdAt: any;
  updatedAt: any;
  createdByUid: string;
}

export interface UserStrategy {
  id: string;
  userId: string;
  strategyId: string;
  strategyName: string;
  brokerAccountId: string;
  brokerName: 'upstox' | 'jainam';
  deployedAmount: number;
  status: 'active' | 'paused' | 'stopped';
  deployedAt: any;
  lastTradedAt: any | null;
  pausedAt: any | null;
  stoppedAt: any | null;
  pausedByAdmin: boolean;
}
