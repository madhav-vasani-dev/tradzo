import { Strategy } from '../../models/strategy.model';

const months2024 = [
  'Jan 2024','Feb 2024','Mar 2024','Apr 2024','May 2024','Jun 2024',
  'Jul 2024','Aug 2024','Sep 2024','Oct 2024','Nov 2024','Dec 2024'
];

function makeMonthly(returns: number[]) {
  return months2024.map((month, i) => ({ month, returnPct: returns[i] }));
}

function makeEquity(returns: number[], start = 300000) {
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
    id: 'nifty-straddle',
    name: 'Nifty Straddle',
    strategyCode: 'NIFTY_STRADDLE',
    description: 'Sells ATM Nifty 50 CE + PE at 12:00 PM every trading day using the current Tuesday weekly expiry. Both legs have a 30% stop-loss placed as SL-M orders at the time of entry. All positions are squared off at 15:29 PM if not already stopped out.',
    category: 'Options',
    instrumentType: 'Nifty 50 Weekly Options',
    riskLevel: 'High',
    isVisible: true,
    minimumAmount: 300000,
    lotSize: 65,
    stopLossPercent: 30,
    entryTime: '12:00',
    exitTime: '15:29',
    tags: ['Intraday', 'Options Selling', 'Straddle', 'ATM'],
    performance: {
      cagr: 45.2,
      sharpeRatio: 1.9,
      maxDrawdown: 11.2,
      winRate: 68.5,
      totalTrades: 240,
      avgTradeReturn: 0.65,
      avgTradeDurationMinutes: 209,
      profitFactor: 2.3,
      calmarRatio: 4.0,
      expectancy: 1950,
      backtestStartDate: '2024-01-01',
      backtestEndDate: '2024-12-31',
      monthlyReturns: makeMonthly([4.2, 3.8, 5.1, 2.9, 4.8, 3.5, 5.2, 4.6, 3.1, 4.9, 3.7, 4.5]),
      yearlyReturns: [{ year: '2024', returnPct: 45.2 }],
      equityCurve: makeEquity([4.2, 3.8, 5.1, 2.9, 4.8, 3.5, 5.2, 4.6, 3.1, 4.9, 3.7, 4.5])
    },
    createdAt: new Date('2024-01-15'),
    updatedAt: new Date('2024-06-01'),
    createdByUid: 'admin-001'
  }
];
