/**
 * Central formatting helpers.
 *
 * All money/date formatting flows through here so the UI is driven by the
 * active strategy/account currency rather than hardcoding one market (INR).
 * Add a currency here and every screen picks it up automatically.
 */

export type CurrencyCode = string; // 'INR' | 'USD' | 'EUR' | ...

interface CurrencyMeta {
  symbol: string;
  /** Locale used for digit grouping (e.g. 1,00,000 for en-IN vs 100,000 for en-US). */
  locale: string;
}

const CURRENCY_META: Record<string, CurrencyMeta> = {
  INR: { symbol: '₹', locale: 'en-IN' },
  USD: { symbol: '$', locale: 'en-US' },
  EUR: { symbol: '€', locale: 'en-IE' },
  GBP: { symbol: '£', locale: 'en-GB' },
  AED: { symbol: 'AED ', locale: 'en-AE' },
  SGD: { symbol: 'S$', locale: 'en-SG' },
  USDT: { symbol: '$', locale: 'en-US' },
};

const DEFAULT_CURRENCY = 'INR';

function meta(currency?: CurrencyCode): CurrencyMeta {
  const code = (currency || DEFAULT_CURRENCY).toUpperCase();
  return CURRENCY_META[code] || { symbol: `${code} `, locale: undefined as any };
}

/** Currency symbol for a code (falls back to the code itself). */
export function currencySymbol(currency?: CurrencyCode): string {
  return meta(currency).symbol;
}

export interface MoneyOptions {
  /** Fixed number of decimals. Default 0. */
  decimals?: number;
  /** Prefix positive values with '+' (useful for PnL). Default false. */
  signed?: boolean;
  /** Include the currency symbol. Default true. */
  showSymbol?: boolean;
}

/**
 * Format a monetary value for the given currency.
 * Currency-agnostic: drives symbol + digit grouping off the currency code.
 */
export function formatMoney(
  value: number | null | undefined,
  currency?: CurrencyCode,
  options: MoneyOptions = {},
): string {
  if (value === null || value === undefined || isNaN(value as number)) return '—';
  const { decimals = 0, signed = false, showSymbol = true } = options;
  const m = meta(currency);
  const abs = Math.abs(value);
  const formatted = new Intl.NumberFormat(m.locale, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(abs);
  const sign = value < 0 ? '-' : signed ? '+' : '';
  return `${sign}${showSymbol ? m.symbol : ''}${formatted}`;
}

/**
 * Format a dual-currency PnL value, e.g. "+$12.50 (+₹1,040)".
 * When no secondary value is supplied, only the primary currency is shown.
 */
export function formatDualMoney(
  primary: number | null | undefined,
  primaryCurrency: CurrencyCode,
  secondary?: number | null,
  secondaryCurrency: CurrencyCode = 'INR',
  decimals = 2,
): string {
  if (primary === null || primary === undefined) return '—';
  const primaryStr = formatMoney(primary, primaryCurrency, { decimals, signed: true });
  if (secondary === undefined || secondary === null) return primaryStr;
  const secondaryStr = formatMoney(secondary, secondaryCurrency, { decimals: 0, signed: true });
  return `${primaryStr} (${secondaryStr})`;
}

/**
 * Format a date using the viewer's locale by default (dynamic, not India-locked).
 */
export function formatDate(
  date: string | number | Date | null | undefined,
  options: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'short', year: 'numeric' },
  locale?: string,
): string {
  if (!date) return '—';
  const d = date instanceof Date ? date : new Date(date);
  if (isNaN(d.getTime())) return '—';
  return d.toLocaleDateString(locale, options);
}
