import { Injectable, inject } from '@angular/core';
import {
  Firestore,
  collection,
  collectionData,
  doc,
  setDoc,
  deleteDoc,
  query,
  where,
  serverTimestamp,
  orderBy,
} from '@angular/fire/firestore';
import { Auth } from '@angular/fire/auth';
import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { Observable, from, firstValueFrom } from 'rxjs';
import { map } from 'rxjs/operators';
import { BACKEND_BASE_URL } from '../config';

// ── Types ─────────────────────────────────────────────────────────────────────

export type ViewMode = 'daily' | 'weekly' | 'monthly';
export type YearRange = 5 | 10 | 15 | 20 | 25 | 'max';

export interface SeasonalityStock {
  symbol: string;
  displayName?: string;
  dataUrl?: string;
  driveFilePresent: boolean;
  driveFileSizeBytes?: number;
  driveFileModified?: string;
  lastAnalysisAt?: string;
  addedAt?: string;
  addedBy?: string;
}

export interface PeriodStats {
  avg: number | null;
  sigma: number | null;
  posProb: number | null;
  negProb: number | null;
  pos_prob?: number | null;
  neg_prob?: number | null;
  count: number;
  streak: number;
}

export interface SeasonalityResult {
  id: string;
  symbol: string;
  viewMode: ViewMode;
  years: YearRange;
  computedAt?: any;
  grid: Record<string, Record<string, number | null>>;   // {year: {period: return%}}
  stats: Record<string, PeriodStats>;                    // {period: stats}
  yearTotals: Record<string, number | null>;
  periodsOrdered: string[];
  years_list: string[];                                  // ordered list of year strings
}

export interface UpcomingTrade {
  symbol: string;
  viewMode: ViewMode;
  period: string;
  entryDate: string;
  exitDate: string | null;
  direction: 'BULL' | 'BEAR';
  posProb: number;
  negProb: number | null;
  avgReturn: number | null;
  sigma: number | null;
  streak: number;
  daysAway: number;
}

export interface AnalysisRunSummary {
  totalCombos: number;
  success: number;
  errors: number;
  details: Record<string, string>;
}

export interface UserSeasonalityConfig {
  id?: string;
  name: string;
  symbols: string[];
  viewMode: ViewMode;
  years: YearRange;
  probabilityThreshold: number;
  lookaheadDays: number;
  createdAt?: any;
}

export interface AnalysisFilters {
  symbols: string[];
  viewMode: ViewMode;
  years: YearRange;
  probabilityThreshold: number;
  lookaheadDays: number;
}


// ── Service ────────────────────────────────────────────────────────────────────

@Injectable({ providedIn: 'root' })
export class SeasonalityService {
  private firestore = inject(Firestore);
  private auth = inject(Auth);
  private http = inject(HttpClient);

  private get apiBase() { return BACKEND_BASE_URL; }

  // ── Auth token helper ──────────────────────────────────────────────────────

  private async authHeaders(): Promise<HttpHeaders> {
    const user = this.auth.currentUser;
    if (!user) throw new Error('Not authenticated');
    const token = await user.getIdToken();
    return new HttpHeaders({ Authorization: `Bearer ${token}` });
  }

  // ── User API ───────────────────────────────────────────────────────────────

  /** List all stocks available for analysis. */
  getStocks(): Observable<SeasonalityStock[]> {
    return from(
      this.authHeaders().then(headers =>
        firstValueFrom(this.http.get<any[]>(`${this.apiBase}/seasonality/stocks`, { headers }))
      )
    ).pipe(
      map(stocks => stocks.map(s => ({
        symbol: s.symbol,
        displayName: s.display_name,
        dataUrl: s.data_url,
        driveFilePresent: s.drive_file_present,
        driveFileSizeBytes: s.drive_file_size_bytes,
        driveFileModified: s.drive_file_modified,
        lastAnalysisAt: s.last_analysis_at,
        addedAt: s.added_at,
        addedBy: s.added_by,
      })))
    );
  }

  /** Fetch cached seasonality results for given filters. */
  getCachedResults(
    symbols: string[],
    viewMode: ViewMode,
    years: YearRange,
    returnBasis: 'open' | 'prev_close' = 'open',
  ): Observable<SeasonalityResult[]> {
    return from(
      this.authHeaders().then(headers => {
        let params = new HttpParams()
          .set('symbols', symbols.join(','))
          .set('view_mode', viewMode)
          .set('years', String(years))
          .set('return_basis', returnBasis);
        return firstValueFrom(
          this.http.get<any[]>(`${this.apiBase}/seasonality/results`, { headers, params })
        );
      })
    ).pipe(map(results => results.map(this._mapResult)));
  }

  /** Fetch upcoming high-probability trades (BULL and BEAR). */
  getUpcomingTrades(
    symbols: string[],
    viewMode: ViewMode,
    years: YearRange,
    probabilityThreshold: number,
    lookaheadDays: number,
    returnBasis: 'open' | 'prev_close' = 'open',
    avgReturnThreshold: number = 0,
    directionFilter: 'ALL' | 'BULL' | 'BEAR' = 'ALL',
  ): Observable<UpcomingTrade[]> {
    return from(
      this.authHeaders().then(headers =>
        firstValueFrom(
          this.http.post<any[]>(
            `${this.apiBase}/seasonality/upcoming-trades`,
            {
              symbols: symbols.length > 0 ? symbols : null,
              view_mode: viewMode,
              years: years === 'max' ? 'max' : years,
              probability_threshold: probabilityThreshold,
              lookahead_days: lookaheadDays,
              return_basis: returnBasis,
              avg_return_threshold: avgReturnThreshold,
              direction_filter: directionFilter,
            },
            { headers }
          )
        )
      )
    ).pipe(map(trades => trades.map(this._mapTrade)));
  }

  // ── Admin API ──────────────────────────────────────────────────────────────

  /** Add a new stock with optional public data URL or file. */
  async addStock(symbol: string, displayName?: string, dataUrl?: string): Promise<void> {
    const headers = await this.authHeaders();
    await firstValueFrom(
      this.http.post(
        `${this.apiBase}/seasonality/admin/stocks`,
        { symbol, display_name: displayName, data_url: dataUrl },
        { headers }
      )
    );
  }

  /** Auto-sync and register all stock CSV files from a public Google Drive folder. */
  async syncDriveFolder(folderUrl?: string): Promise<any> {
    const headers = await this.authHeaders();
    const form = new FormData();
    if (folderUrl) {
      form.append('folder_url', folderUrl);
    }
    const uploadHeaders = new HttpHeaders({ Authorization: headers.get('Authorization')! });
    return await firstValueFrom(
      this.http.post(`${this.apiBase}/seasonality/admin/sync-drive-folder`, form, { headers: uploadHeaders })
    );
  }

  /** Upload a CSV file or provide a public URL for a stock. */
  async uploadStockFile(symbol: string, file?: File | null, dataUrl?: string): Promise<void> {
    const headers = await this.authHeaders();
    const form = new FormData();
    form.append('symbol', symbol);
    if (file) {
      form.append('file', file);
    }
    if (dataUrl) {
      form.append('data_url', dataUrl);
    }
    const uploadHeaders = new HttpHeaders({ Authorization: headers.get('Authorization')! });
    await firstValueFrom(
      this.http.post(`${this.apiBase}/seasonality/admin/upload`, form, { headers: uploadHeaders })
    );
  }

  /** Remove a stock from the watchlist and delete its Drive file. */
  async removeStock(symbol: string): Promise<void> {
    const headers = await this.authHeaders();
    await firstValueFrom(
      this.http.delete(`${this.apiBase}/seasonality/admin/stocks/${symbol}`, { headers })
    );
  }

  /** Auto-import all 500+ stocks from ind_nifty500list.csv into watchlist. */
  async syncNifty500List(): Promise<{ status: string; stocks_added: number; stocks_updated: number; total_drive_files_matched: number }> {
    const headers = await this.authHeaders();
    return firstValueFrom(
      this.http.post<any>(
        `${this.apiBase}/seasonality/admin/sync-nifty500`,
        {},
        { headers }
      )
    );
  }

  /** Trigger full seasonality analysis with live streaming progress. */
  async triggerAnalysis(
    viewModes: ViewMode[],
    yearRanges: (number | string)[],
    onProgress?: (event: { type: string; done: number; total: number; symbol?: string; status?: string }) => void,
  ): Promise<AnalysisRunSummary> {
    const user = this.auth.currentUser;
    if (!user) throw new Error('Not authenticated');
    const token = await user.getIdToken();

    const response = await fetch(`${this.apiBase}/seasonality/admin/run-analysis/stream`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ view_modes: viewModes, year_ranges: yearRanges }),
    });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`Analysis failed (HTTP ${response.status}): ${errText}`);
    }

    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let lastEvent: any = { done: 0, total: 0 };
    let success = 0;
    let errors = 0;

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';  // keep incomplete line

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        try {
          const event = JSON.parse(trimmed);
          lastEvent = event;
          if (event.type === 'combo') {
            if (event.status === 'ok') success++; else errors++;
          }
          if (onProgress) onProgress(event);
        } catch { /* skip malformed lines */ }
      }
    }

    return {
      totalCombos: lastEvent.total ?? 0,
      success,
      errors,
      details: {},
    };
  }

  // ── Firestore: User saved configs ──────────────────────────────────────────

  getUserConfigs(): Observable<UserSeasonalityConfig[]> {
    const user = this.auth.currentUser;
    if (!user) return new Observable(sub => sub.next([]));

    const col = collection(this.firestore, 'userSeasonalityConfigs');
    const q = query(col, where('uid', '==', user.uid), orderBy('createdAt', 'desc'));
    return collectionData(q, { idField: 'id' }) as Observable<UserSeasonalityConfig[]>;
  }

  async saveUserConfig(config: Omit<UserSeasonalityConfig, 'id' | 'createdAt'>): Promise<void> {
    const user = this.auth.currentUser;
    if (!user) throw new Error('Not authenticated');

    const col = collection(this.firestore, 'userSeasonalityConfigs');
    const docRef = doc(col);
    await setDoc(docRef, {
      ...config,
      uid: user.uid,
      createdAt: serverTimestamp(),
    });
  }

  async deleteUserConfig(configId: string): Promise<void> {
    const docRef = doc(this.firestore, `userSeasonalityConfigs/${configId}`);
    await deleteDoc(docRef);
  }

  // ── Firestore: User watchlist bookmarks ────────────────────────────────────

  getWatchlist(): Observable<any[]> {
    const user = this.auth.currentUser;
    if (!user) return new Observable(sub => sub.next([]));

    const col = collection(this.firestore, 'userSeasonalityWatchlist');
    const q = query(col, where('uid', '==', user.uid));
    return collectionData(q, { idField: 'id' }) as Observable<any[]>;
  }

  async addToWatchlist(trade: Partial<UpcomingTrade>): Promise<void> {
    const user = this.auth.currentUser;
    if (!user) throw new Error('Not authenticated');

    const col = collection(this.firestore, 'userSeasonalityWatchlist');
    const docRef = doc(col);
    await setDoc(docRef, {
      ...trade,
      uid: user.uid,
      addedAt: serverTimestamp(),
    });
  }

  async removeFromWatchlist(watchlistId: string): Promise<void> {
    const docRef = doc(this.firestore, `userSeasonalityWatchlist/${watchlistId}`);
    await deleteDoc(docRef);
  }

  // ── Private mappers ────────────────────────────────────────────────────────

  private _mapResult(r: any): SeasonalityResult {
    const gridObj = r.grid || {};
    const yearsArr = Array.isArray(r.years) ? r.years : (r.years_list && Array.isArray(r.years_list) ? r.years_list : Object.keys(gridObj));
    return {
      id: r.id || '',
      symbol: r.symbol || '',
      viewMode: r.viewMode || r.view_mode || 'monthly',
      years: r.years,
      computedAt: r.computedAt,
      grid: gridObj,
      stats: r.stats || {},
      yearTotals: r.year_totals || r.yearTotals || {},
      periodsOrdered: r.periods_ordered || r.periodsOrdered || [],
      years_list: yearsArr,
    };
  }

  private _mapTrade(t: any): UpcomingTrade {
    return {
      symbol: t.symbol,
      viewMode: t.viewMode || t.view_mode,
      period: t.period,
      entryDate: t.entryDate || t.entry_date,
      exitDate: t.exitDate || t.exit_date,
      direction: t.direction,
      posProb: t.posProb ?? t.pos_prob,
      negProb: t.negProb ?? t.neg_prob,
      avgReturn: t.avgReturn ?? t.avg_return,
      sigma: t.sigma,
      streak: t.streak,
      daysAway: t.daysAway ?? t.days_away,
    };
  }
}
