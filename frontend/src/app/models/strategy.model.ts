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
  lotSize: number;          // Units per lot (e.g. 65 for Nifty)
  strategyCode: string;     // Matches backend REGISTRY key (e.g. 'NIFTY_STRADDLE')
  stopLossPercent: number;  // e.g. 30
  entryTime: string;        // 'HH:MM'
  exitTime: string;         // 'HH:MM'
  tags: string[];
  performance: StrategyPerformance;
  createdAt: any;
  updatedAt: any;
  createdByUid: string;
}

/** Status of a deployed strategy for a user throughout the trading day. */
export type UserStrategyStatus = 'enabled' | 'ready' | 'trade_active' | 'trade_closed' | 'paused' | 'stopped';

export interface UserStrategy {
  id: string;
  userId: string;
  strategyId: string;
  strategyCode: string;
  strategyName: string;
  brokerAccountId: string;
  brokerName: 'upstox' | 'jainam';
  deployedAmount: number;
  multiplier: number;           // 1 = 1 lot, 2 = 2 lots, etc.
  status: UserStrategyStatus;   // live state machine status
  statusUpdatedAt: any;
  deployedAt: any;
  pausedByAdmin: boolean;
  lastTradedAt?: any | null;
  pausedAt?: any | null;
  stoppedAt?: any | null;
}

/** A single open/closed option leg for a user's deployed strategy. */
export interface Position {
  id: string;
  date: string;             // 'YYYY-MM-DD'
  userId: string;
  strategyId: string;
  strategyCode: string;
  userStrategyId: string;
  brokerAccountId: string;
  broker: string;
  instrumentKey: string;
  symbol: string;
  optionType: 'CE' | 'PE';
  strike: number;
  expiry: string;
  quantity: number;
  lots: number;
  entryPrice: number;
  slPrice: number;
  entryOrderId: string;
  slOrderId: string;
  status: 'open' | 'sl_hit' | 'squared_off' | 'error';
  exitReason: string | null;
  exitOrderId: string | null;
  exitPrice: number | null;
  exitAt: any | null;
  pnl: number | null;
  entryAt: any;
  isPaper: boolean;
}
