import { Strategy } from '../../models/strategy.model';

const months2024 = [
  'Jan 2024','Feb 2024','Mar 2024','Apr 2024','May 2024','Jun 2024',
  'Jul 2024','Aug 2024','Sep 2024','Oct 2024','Nov 2024','Dec 2024'
];

function makeMonthly(returns: number[]) {
  return months2024.map((month, i) => ({ month, returnPct: returns[i] }));
}

function makeEquity(returns: number[], start = 100000) {
  const curve = [{ date: '2024-01-01', value: start }];
  let val = start;
  returns.forEach((r, i) => {
    val = val * (1 + r / 100);
    const d = new Date(2024, i + 1, 1);
    curve.push({ date: d.toISOString().split('T')[0], value: Math.round(val) });
  });
  return curve;
}

export const MOCK_STRATEGIES: Strategy[] = [
  {
    id: 'str-001',
    name: 'Nifty Iron Condor',
    description: 'A premium-collection options strategy that sells an OTM call spread and OTM put spread on Nifty index simultaneously. Profits when Nifty stays range-bound. Best suited for low-volatility, sideways markets with a defined max risk.',
    category: 'Options',
    instrumentType: 'Nifty 50 Options',
    riskLevel: 'Low',
    isVisible: true,
    minimumAmount: 100000,
    tags: ['Intraday', 'Options Selling', 'Range Bound'],
    performance: {
      cagr: 38.4,
      sharpeRatio: 2.1,
      maxDrawdown: 8.2,
      winRate: 72.5,
      totalTrades: 248,
      avgTradeReturn: 0.52,
      avgTradeDurationMinutes: 240,
      profitFactor: 2.6,
      calmarRatio: 4.7,
      expectancy: 1240,
      backtestStartDate: '2024-01-01',
      backtestEndDate: '2024-12-31',
      monthlyReturns: makeMonthly([3.2, 2.8, 4.1, 1.9, 3.8, 2.5, 4.2, 3.6, 2.1, 3.9, 2.7, 3.5]),
      yearlyReturns: [{ year: '2024', returnPct: 38.4 }],
      equityCurve: makeEquity([3.2, 2.8, 4.1, 1.9, 3.8, 2.5, 4.2, 3.6, 2.1, 3.9, 2.7, 3.5])
    },
    createdAt: new Date('2024-01-15'),
    updatedAt: new Date('2024-06-01'),
    createdByUid: 'admin-001'
  },
  {
    id: 'str-002',
    name: 'BankNifty Momentum Scalper',
    description: 'High-frequency intraday momentum strategy on BankNifty. Uses 1-minute VWAP deviation and RSI signals to enter short-duration trades in the direction of prevailing trend. Exits positions before 3:00 PM.',
    category: 'Options',
    instrumentType: 'BankNifty Options',
    riskLevel: 'High',
    isVisible: true,
    minimumAmount: 200000,
    tags: ['Intraday', 'Momentum', 'Scalping'],
    performance: {
      cagr: 67.2,
      sharpeRatio: 1.4,
      maxDrawdown: 22.5,
      winRate: 58.3,
      totalTrades: 612,
      avgTradeReturn: 0.38,
      avgTradeDurationMinutes: 45,
      profitFactor: 1.9,
      calmarRatio: 2.99,
      expectancy: 820,
      backtestStartDate: '2024-01-01',
      backtestEndDate: '2024-12-31',
      monthlyReturns: makeMonthly([7.1, -2.3, 8.4, 5.2, -1.8, 9.3, 6.7, -3.1, 11.2, 4.8, 7.5, 5.2]),
      yearlyReturns: [{ year: '2024', returnPct: 67.2 }],
      equityCurve: makeEquity([7.1, -2.3, 8.4, 5.2, -1.8, 9.3, 6.7, -3.1, 11.2, 4.8, 7.5, 5.2])
    },
    createdAt: new Date('2024-02-10'),
    updatedAt: new Date('2024-07-15'),
    createdByUid: 'admin-001'
  },
  {
    id: 'str-003',
    name: 'Nifty Weekly Expiry Straddle',
    description: 'Sells ATM straddle on Nifty every Monday morning and hedges with OTM wings. Adjusts delta dynamically using 15-minute candle signals. Designed to capture weekly time decay while managing gap risk.',
    category: 'Options',
    instrumentType: 'Nifty 50 Weekly Options',
    riskLevel: 'Medium',
    isVisible: true,
    minimumAmount: 150000,
    tags: ['Weekly Expiry', 'Theta', 'Delta Neutral'],
    performance: {
      cagr: 52.1,
      sharpeRatio: 1.85,
      maxDrawdown: 14.7,
      winRate: 65.8,
      totalTrades: 186,
      avgTradeReturn: 0.91,
      avgTradeDurationMinutes: 1440,
      profitFactor: 2.2,
      calmarRatio: 3.55,
      expectancy: 2100,
      backtestStartDate: '2024-01-01',
      backtestEndDate: '2024-12-31',
      monthlyReturns: makeMonthly([4.8, 3.2, -1.5, 6.1, 4.4, 5.2, 3.8, 4.9, 2.2, 5.7, 4.1, 5.1]),
      yearlyReturns: [{ year: '2024', returnPct: 52.1 }],
      equityCurve: makeEquity([4.8, 3.2, -1.5, 6.1, 4.4, 5.2, 3.8, 4.9, 2.2, 5.7, 4.1, 5.1])
    },
    createdAt: new Date('2024-03-01'),
    updatedAt: new Date('2024-08-20'),
    createdByUid: 'admin-001'
  },
  {
    id: 'str-004',
    name: 'Nifty Futures Trend Rider',
    description: 'Positional trend-following strategy on Nifty Futures. Uses EMA crossover (20/50) on 1-hour charts with ATR-based stops. Holds positions for 1–5 days. Not intraday — overnight positions are held.',
    category: 'Futures',
    instrumentType: 'Nifty 50 Futures',
    riskLevel: 'Medium',
    isVisible: true,
    minimumAmount: 120000,
    tags: ['Positional', 'Trend Following', 'EMA Crossover'],
    performance: {
      cagr: 44.6,
      sharpeRatio: 1.62,
      maxDrawdown: 16.3,
      winRate: 54.2,
      totalTrades: 134,
      avgTradeReturn: 1.24,
      avgTradeDurationMinutes: 3600,
      profitFactor: 2.1,
      calmarRatio: 2.74,
      expectancy: 1850,
      backtestStartDate: '2024-01-01',
      backtestEndDate: '2024-12-31',
      monthlyReturns: makeMonthly([5.2, -2.1, 6.8, 3.4, 4.9, -1.2, 7.1, 4.5, 2.8, 5.9, 3.2, 4.7]),
      yearlyReturns: [{ year: '2024', returnPct: 44.6 }],
      equityCurve: makeEquity([5.2, -2.1, 6.8, 3.4, 4.9, -1.2, 7.1, 4.5, 2.8, 5.9, 3.2, 4.7])
    },
    createdAt: new Date('2024-03-15'),
    updatedAt: new Date('2024-09-01'),
    createdByUid: 'admin-001'
  },
  {
    id: 'str-005',
    name: 'Nifty ORB Breakout',
    description: 'Opening Range Breakout strategy on Nifty. Identifies the high/low of the first 15 minutes post-open and enters in the direction of the breakout. Uses Fibonacci targets with tight stoploss at range midpoint.',
    category: 'Index',
    instrumentType: 'Nifty 50',
    riskLevel: 'Low',
    isVisible: true,
    minimumAmount: 75000,
    tags: ['Intraday', 'ORB', 'Breakout'],
    performance: {
      cagr: 29.8,
      sharpeRatio: 2.3,
      maxDrawdown: 6.4,
      winRate: 63.1,
      totalTrades: 198,
      avgTradeReturn: 0.44,
      avgTradeDurationMinutes: 180,
      profitFactor: 2.4,
      calmarRatio: 4.66,
      expectancy: 980,
      backtestStartDate: '2024-01-01',
      backtestEndDate: '2024-12-31',
      monthlyReturns: makeMonthly([2.4, 2.1, 3.2, 1.8, 2.9, 2.5, 3.1, 2.7, 1.9, 3.4, 2.2, 2.8]),
      yearlyReturns: [{ year: '2024', returnPct: 29.8 }],
      equityCurve: makeEquity([2.4, 2.1, 3.2, 1.8, 2.9, 2.5, 3.1, 2.7, 1.9, 3.4, 2.2, 2.8])
    },
    createdAt: new Date('2024-04-01'),
    updatedAt: new Date('2024-10-01'),
    createdByUid: 'admin-001'
  },
  {
    id: 'str-006',
    name: 'BankNifty Put Credit Spread',
    description: 'Sells OTM put spreads on BankNifty every week, targeting weekly theta decay. Enters on Tuesday morning and exits on Thursday or at 50% profit / 2x loss. Designed for bullish-to-neutral market conditions.',
    category: 'Options',
    instrumentType: 'BankNifty Weekly Options',
    riskLevel: 'Low',
    isVisible: true,
    minimumAmount: 80000,
    tags: ['Weekly', 'Credit Spread', 'Bullish'],
    performance: {
      cagr: 34.7,
      sharpeRatio: 2.05,
      maxDrawdown: 9.1,
      winRate: 70.2,
      totalTrades: 156,
      avgTradeReturn: 0.73,
      avgTradeDurationMinutes: 2880,
      profitFactor: 2.45,
      calmarRatio: 3.81,
      expectancy: 1450,
      backtestStartDate: '2024-01-01',
      backtestEndDate: '2024-12-31',
      monthlyReturns: makeMonthly([3.1, 2.5, 3.8, 2.2, 3.4, 2.8, 3.6, 2.9, 1.8, 3.7, 2.4, 3.2]),
      yearlyReturns: [{ year: '2024', returnPct: 34.7 }],
      equityCurve: makeEquity([3.1, 2.5, 3.8, 2.2, 3.4, 2.8, 3.6, 2.9, 1.8, 3.7, 2.4, 3.2])
    },
    createdAt: new Date('2024-05-01'),
    updatedAt: new Date('2024-11-01'),
    createdByUid: 'admin-001'
  }
];
