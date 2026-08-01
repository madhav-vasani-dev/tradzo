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

export type StrategyCategory = 'Options' | 'Futures' | 'Equity' | 'Index' | 'Crypto';
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
  lotSize: number;          // Units per lot (e.g. 1 for Delta, 65 for Nifty)
  strategyCode: string;     // Matches backend REGISTRY key (e.g. 'NIFTY_STRADDLE')
  stopLossPercent: number;  // e.g. 30 or 100
  entryTime: string;        // 'HH:MM'
  exitTime: string;         // 'HH:MM'
  tags: string[];
  performance: StrategyPerformance;
  createdAt: any;
  updatedAt: any;
  createdByUid: string;
  /** Broker required for this strategy ('upstox' | 'jainam' | 'delta'). Default: 'upstox' */
  broker?: string;
  /** Settlement currency for PnL display. Default: 'INR' */
  currency?: 'INR' | 'USD';
  /** If true, PnL is stored in USD with a parallel INR equivalent field. */
  dualCurrencyPnl?: boolean;
  /** If true, displays an asterisk (*) next to minimum investment indicating it varies with lot count. */
  hasLotAsterisk?: boolean;
  /** Optional note displayed below the equity curve chart (e.g. "* Equity curve is based on 100 lots"). */
  equityNote?: string;
  /**
   * Underlying units represented by a single unit of a trade's `quantity`.
   * Lets the UI show size in the underlying (e.g. 0.001 BTC per contract → 100 qty = 0.1 BTC).
   */
  contractNotional?: number;
  /** Symbol of the underlying used with contractNotional (e.g. 'BTC'). */
  underlyingSymbol?: string;
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
  brokerName: 'upstox' | 'jainam' | 'delta';
  deployedAmount: number;
  multiplier: number;           // 1 = 1 lot, 2 = 2 lots, etc.
  status: UserStrategyStatus;   // live state machine status
  statusUpdatedAt: any;
  deployedAt: any;
  pausedByAdmin: boolean;
  lastTradedAt?: any | null;
  pausedAt?: any | null;
  stoppedAt?: any | null;
  /** Settlement/display currency for this deployment. Falls back to 'INR' when absent. */
  currency?: string;
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
  /** Booked P&L — only set once the position closes. Use `unrealizedPnl` while open. */
  pnl: number | null;
  entryAt: any;
  isPaper: boolean;
  /** Last traded price, streamed from the broker websocket while the position is open. */
  ltp?: number | null;
  ltpInr?: number | null;
  /** Mark-to-market P&L on an open position, refreshed every few seconds. */
  unrealizedPnl?: number | null;
  unrealizedPnlInr?: number | null;
  /** When `unrealizedPnl` was last marked. */
  pnlUpdatedAt?: any | null;
  /** Native settlement currency for prices/PnL on this position. Falls back to 'INR' when absent. */
  currency?: string;
  /** INR equivalents (populated for non-INR-settled instruments, e.g. crypto). Preferred for display. */
  entryPriceInr?: number | null;
  slPriceInr?: number | null;
  exitPriceInr?: number | null;
  pnlInr?: number | null;
  usdToInrRate?: number | null;
}
