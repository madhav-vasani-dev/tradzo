import { Strategy } from '../../models/strategy.model';

const MONTHLY_PROFITS = [
  {"year": "2019", "month": "Jan", "profit": 0},
  {"year": "2019", "month": "Feb", "profit": 1956},
  {"year": "2019", "month": "Mar", "profit": 9779},
  {"year": "2019", "month": "Apr", "profit": 9880},
  {"year": "2019", "month": "May", "profit": 14004},
  {"year": "2019", "month": "Jun", "profit": 9288},
  {"year": "2019", "month": "Jul", "profit": -2479},
  {"year": "2019", "month": "Aug", "profit": 4205},
  {"year": "2019", "month": "Sep", "profit": 16828},
  {"year": "2019", "month": "Oct", "profit": 1413},
  {"year": "2019", "month": "Nov", "profit": -2021},
  {"year": "2019", "month": "Dec", "profit": -87},
  {"year": "2020", "month": "Jan", "profit": 10536},
  {"year": "2020", "month": "Feb", "profit": 14592},
  {"year": "2020", "month": "Mar", "profit": 35083},
  {"year": "2020", "month": "Apr", "profit": 15619},
  {"year": "2020", "month": "May", "profit": 10039},
  {"year": "2020", "month": "Jun", "profit": 8245},
  {"year": "2020", "month": "Jul", "profit": 17117},
  {"year": "2020", "month": "Aug", "profit": 13643},
  {"year": "2020", "month": "Sep", "profit": 8482},
  {"year": "2020", "month": "Oct", "profit": 6340},
  {"year": "2020", "month": "Nov", "profit": 4085},
  {"year": "2020", "month": "Dec", "profit": 14173},
  {"year": "2021", "month": "Jan", "profit": 11271},
  {"year": "2021", "month": "Feb", "profit": 9090},
  {"year": "2021", "month": "Mar", "profit": 10903},
  {"year": "2021", "month": "Apr", "profit": 19298},
  {"year": "2021", "month": "May", "profit": 12623},
  {"year": "2021", "month": "Jun", "profit": 5518},
  {"year": "2021", "month": "Jul", "profit": 7647},
  {"year": "2021", "month": "Aug", "profit": 10478},
  {"year": "2021", "month": "Sep", "profit": 12710},
  {"year": "2021", "month": "Oct", "profit": 21875},
  {"year": "2021", "month": "Nov", "profit": -3159},
  {"year": "2021", "month": "Dec", "profit": -8108},
  {"year": "2022", "month": "Jan", "profit": 42},
  {"year": "2022", "month": "Feb", "profit": 9256},
  {"year": "2022", "month": "Mar", "profit": 11573},
  {"year": "2022", "month": "Apr", "profit": -8684},
  {"year": "2022", "month": "May", "profit": 19994},
  {"year": "2022", "month": "Jun", "profit": 10377},
  {"year": "2022", "month": "Jul", "profit": 11316},
  {"year": "2022", "month": "Aug", "profit": 4520},
  {"year": "2022", "month": "Sep", "profit": -6909},
  {"year": "2022", "month": "Oct", "profit": 8401},
  {"year": "2022", "month": "Nov", "profit": 3389},
  {"year": "2022", "month": "Dec", "profit": 4761},
  {"year": "2023", "month": "Jan", "profit": -6376},
  {"year": "2023", "month": "Feb", "profit": -2398},
  {"year": "2023", "month": "Mar", "profit": -692},
  {"year": "2023", "month": "Apr", "profit": 620},
  {"year": "2023", "month": "May", "profit": -4244},
  {"year": "2023", "month": "Jun", "profit": -1774},
  {"year": "2023", "month": "Jul", "profit": 2661},
  {"year": "2023", "month": "Aug", "profit": 6077},
  {"year": "2023", "month": "Sep", "profit": 783},
  {"year": "2023", "month": "Oct", "profit": 3714},
  {"year": "2023", "month": "Nov", "profit": 2694},
  {"year": "2023", "month": "Dec", "profit": 8290},
  {"year": "2024", "month": "Jan", "profit": 8209},
  {"year": "2024", "month": "Feb", "profit": 25535},
  {"year": "2024", "month": "Mar", "profit": 16204},
  {"year": "2024", "month": "Apr", "profit": 7920},
  {"year": "2024", "month": "May", "profit": 5993},
  {"year": "2024", "month": "Jun", "profit": 234},
  {"year": "2024", "month": "Jul", "profit": -1075},
  {"year": "2024", "month": "Aug", "profit": 15843},
  {"year": "2024", "month": "Sep", "profit": -7631},
  {"year": "2024", "month": "Oct", "profit": 19093},
  {"year": "2024", "month": "Nov", "profit": 17280},
  {"year": "2024", "month": "Dec", "profit": 32769},
  {"year": "2025", "month": "Jan", "profit": 5122},
  {"year": "2025", "month": "Feb", "profit": 25116},
  {"year": "2025", "month": "Mar", "profit": 7445},
  {"year": "2025", "month": "Apr", "profit": -3295},
  {"year": "2025", "month": "May", "profit": 16094},
  {"year": "2025", "month": "Jun", "profit": 3799},
  {"year": "2025", "month": "Jul", "profit": 10741},
  {"year": "2025", "month": "Aug", "profit": 4104},
  {"year": "2025", "month": "Sep", "profit": 4598},
  {"year": "2025", "month": "Oct", "profit": 15135},
  {"year": "2025", "month": "Nov", "profit": 7072},
  {"year": "2025", "month": "Dec", "profit": 1686},
  {"year": "2026", "month": "Jan", "profit": 6519},
  {"year": "2026", "month": "Feb", "profit": 17127},
  {"year": "2026", "month": "Mar", "profit": 620},
  {"year": "2026", "month": "Apr", "profit": 18720},
  {"year": "2026", "month": "May", "profit": 1680},
  {"year": "2026", "month": "Jun", "profit": 20185},
  {"year": "2026", "month": "Jul", "profit": 8924},
];

const START_CAPITAL = 300000.0;

const monthlyReturns = MONTHLY_PROFITS.map(item => ({
  month: `${item.month} ${item.year}`,
  returnPct: round((item.profit / START_CAPITAL) * 100, 2)
}));

const yearlyProfits: Record<string, number> = {};
MONTHLY_PROFITS.forEach(item => {
  yearlyProfits[item.year] = (yearlyProfits[item.year] || 0) + item.profit;
});

const yearlyReturns = Object.keys(yearlyProfits).sort().map(yr => ({
  year: yr,
  returnPct: round((yearlyProfits[yr] / START_CAPITAL) * 100, 2)
}));

let currentEquity = START_CAPITAL;
const monthNums: Record<string, string> = {
  Jan: "01", Feb: "02", Mar: "03", Apr: "04", May: "05", Jun: "06",
  Jul: "07", Aug: "08", Sep: "09", Oct: "10", Nov: "11", Dec: "12"
};

const equityCurve = [{"date": "2019-01-01", "value": START_CAPITAL}];
MONTHLY_PROFITS.forEach(item => {
  currentEquity += item.profit;
  equityCurve.push({
    date: `${item.year}-${monthNums[item.month]}-28`,
    value: round(currentEquity, 2)
  });
});

function round(value: number, decimals: number): number {
  return Number(Math.round(Number(value + 'e' + decimals)) + 'e-' + decimals);
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
    minimumAmount: START_CAPITAL,
    lotSize: 65,
    stopLossPercent: 30,
    entryTime: '12:00',
    exitTime: '15:29',
    tags: ['Intraday', 'Options Selling', 'Straddle', 'ATM'],
    performance: {
      cagr: 13.63,
      sharpeRatio: 1.45,
      maxDrawdown: 8.50,
      winRate: 64.80,
      totalTrades: 1824,
      avgTradeReturn: 0.13,
      avgTradeDurationMinutes: 209,
      profitFactor: 1.80,
      calmarRatio: 1.60,
      expectancy: 0.28,
      backtestStartDate: '2019-01-01',
      backtestEndDate: '2026-07-12',
      monthlyReturns: monthlyReturns,
      yearlyReturns: yearlyReturns,
      equityCurve: equityCurve
    },
    createdAt: new Date('2019-01-15'),
    updatedAt: new Date('2026-07-12'),
    createdByUid: 'system'
  },
  {
    id: 'btc-option-selling',
    name: 'BTC Option Selling',
    strategyCode: 'BTC_OPTION_SELLING',
    description: 'Sells ATM BTC Call + Put options on Delta Exchange at 17:01 IST every trading day using the current day\'s expiry. Each leg has a 100% stop-loss (doubles the premium) placed as a stop-market order at entry. Positions are squared off at 17:29 IST. PnL is displayed in INR.',
    category: 'Crypto',
    instrumentType: 'BTC Daily Options (Delta Exchange)',
    riskLevel: 'High',
    isVisible: true,
    minimumAmount: 7000,    // ₹7,000 base margin for 100 lots
    hasLotAsterisk: true,   // Displays * next to minimum investment
    equityNote: '* Note: Equity curve & backtest performance is based on 100 lots.',
    lotSize: 1,             // 1 Delta contract (0.001 BTC notional)
    stopLossPercent: 100,
    entryTime: '17:01',
    exitTime: '17:29',
    broker: 'delta',
    currency: 'INR',        // trades settle in USD but are displayed in INR
    dualCurrencyPnl: false,
    contractNotional: 0.001, // 0.001 BTC per contract → 100 qty = 0.1 BTC
    underlyingSymbol: 'BTC',
    tags: ['Intraday', 'Crypto', 'Options Selling', 'Straddle', 'ATM', 'BTC', 'Delta Exchange'],
    performance: {
      cagr: 18.20,
      sharpeRatio: 1.59,
      maxDrawdown: 5.92,
      winRate: 70.88,
      totalTrades: 570,
      avgTradeReturn: 0.52,
      avgTradeDurationMinutes: 28,
      profitFactor: 1.59,
      calmarRatio: 3.07,
      expectancy: 0.84,
      backtestStartDate: '2025-01-01',
      backtestEndDate: '2026-07-24',
      monthlyReturns: [
        { month: 'Jan 2025', returnPct: 31.83 },
        { month: 'Feb 2025', returnPct: 22.94 },
        { month: 'Mar 2025', returnPct: 35.31 },
        { month: 'Apr 2025', returnPct: 16.92 },
        { month: 'May 2025', returnPct: 19.73 },
        { month: 'Jun 2025', returnPct: 21.70 },
        { month: 'Jul 2025', returnPct: 20.37 },
        { month: 'Aug 2025', returnPct: 19.11 },
        { month: 'Sep 2025', returnPct: 7.47 },
        { month: 'Oct 2025', returnPct: 22.09 },
        { month: 'Nov 2025', returnPct: 29.12 },
        { month: 'Dec 2025', returnPct: 13.02 },
        { month: 'Jan 2026', returnPct: 5.79 },
        { month: 'Feb 2026', returnPct: 14.08 },
        { month: 'Mar 2026', returnPct: 4.35 },
        { month: 'Apr 2026', returnPct: 2.87 },
        { month: 'May 2026', returnPct: 8.15 },
        { month: 'Jun 2026', returnPct: -2.00 },
        { month: 'Jul 2026', returnPct: 3.19 },
      ],
      yearlyReturns: [
        { year: '2025', returnPct: 259.61 },
        { year: '2026', returnPct: 36.43 },
      ],
      equityCurve: [
        { date: '2025-01-01', value: 70000 },
        { date: '2025-01-28', value: 92279 },
        { date: '2025-02-28', value: 108338 },
        { date: '2025-03-28', value: 133055 },
        { date: '2025-04-28', value: 144901 },
        { date: '2025-05-28', value: 158714 },
        { date: '2025-06-28', value: 173902 },
        { date: '2025-07-28', value: 188160 },
        { date: '2025-08-28', value: 201540 },
        { date: '2025-09-28', value: 206766 },
        { date: '2025-10-28', value: 222228 },
        { date: '2025-11-28', value: 242610 },
        { date: '2025-12-28', value: 251723 },
        { date: '2026-01-28', value: 255776 },
        { date: '2026-02-28', value: 265632 },
        { date: '2026-03-28', value: 268674 },
        { date: '2026-04-28', value: 270683 },
        { date: '2026-05-28', value: 276390 },
        { date: '2026-06-28', value: 274990 },
        { date: '2026-07-24', value: 277233.30 },
      ]
    },
    createdAt: new Date('2026-07-25'),
    updatedAt: new Date('2026-07-25'),
    createdByUid: 'system'
  }
];
