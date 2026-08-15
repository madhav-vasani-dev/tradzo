import { Component, Input, OnInit, OnChanges, OnDestroy, SimpleChanges, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Subscription } from 'rxjs';
import { TooltipModule } from 'primeng/tooltip';
import { ToastModule } from 'primeng/toast';
import { MessageService } from 'primeng/api';
import { UpcomingTrade, SeasonalityService } from '../../../core/services/seasonality.service';

interface CalendarDay {
  iso: string;
  dayNum: number;
  inRange: boolean;
  isToday: boolean;
  bullCount: number;
  bearCount: number;
}

interface CalendarMonth {
  label: string;
  weeks: (CalendarDay | null)[][];
}

@Component({
  selector: 'app-seasonality-upcoming-trades',
  standalone: true,
  imports: [CommonModule, TooltipModule, ToastModule],
  providers: [MessageService],
  templateUrl: './seasonality-upcoming-trades.component.html',
  styleUrl: './seasonality-upcoming-trades.component.scss',
})
export class SeasonalityUpcomingTradesComponent implements OnInit, OnChanges, OnDestroy {
  @Input() trades: UpcomingTrade[] = [];
  @Input() lookaheadDays = 30;

  private seasonalityService = inject(SeasonalityService);
  private messageService = inject(MessageService);
  private sub?: Subscription;

  watchlistedIds = new Set<string>();
  calendarMonths: CalendarMonth[] = [];
  selectedDate: string | null = null;

  ngOnInit(): void {
    // Live Firestore query — keeps the bookmark icon in sync with what's actually saved.
    this.sub = this.seasonalityService.getWatchlist().subscribe({
      next: (items) => this.watchlistedIds = new Set(items.map((i: any) => `${i.symbol}_${i.period}`)),
      error: () => {},
    });
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['trades'] || changes['lookaheadDays']) {
      this.selectedDate = null;
      this.buildCalendar();
    }
  }

  ngOnDestroy(): void { this.sub?.unsubscribe(); }

  get groupedTrades(): { symbol: string; trades: UpcomingTrade[] }[] {
    const source = this.selectedDate
      ? this.trades.filter(t => t.entryDate?.slice(0, 10) === this.selectedDate)
      : this.trades;

    const map = new Map<string, UpcomingTrade[]>();
    for (const t of source) {
      if (!map.has(t.symbol)) map.set(t.symbol, []);
      map.get(t.symbol)!.push(t);
    }
    return Array.from(map.entries()).map(([symbol, trades]) => ({ symbol, trades }));
  }

  // ── Calendar (today → +lookaheadDays, weekday-aligned since these are real dates) ──
  private buildCalendar(): void {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const rangeEnd = new Date(today);
    rangeEnd.setDate(rangeEnd.getDate() + this.lookaheadDays);

    const countsByDate = new Map<string, { bull: number; bear: number }>();
    for (const t of this.trades) {
      if (!t.entryDate) continue;
      const key = t.entryDate.slice(0, 10);
      const entry = countsByDate.get(key) ?? { bull: 0, bear: 0 };
      if (t.direction === 'BULL') entry.bull++; else entry.bear++;
      countsByDate.set(key, entry);
    }

    const months: CalendarMonth[] = [];
    let cursor = new Date(today.getFullYear(), today.getMonth(), 1);
    const lastMonth = new Date(rangeEnd.getFullYear(), rangeEnd.getMonth(), 1);

    while (cursor <= lastMonth) {
      months.push(this.buildMonth(cursor, today, rangeEnd, countsByDate));
      cursor = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1);
    }
    this.calendarMonths = months;
  }

  private buildMonth(
    monthStart: Date, rangeStart: Date, rangeEnd: Date,
    countsByDate: Map<string, { bull: number; bear: number }>,
  ): CalendarMonth {
    const year = monthStart.getFullYear();
    const month = monthStart.getMonth();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const firstWeekday = (monthStart.getDay() + 6) % 7; // Mon=0..Sun=6

    const days: (CalendarDay | null)[] = new Array(firstWeekday).fill(null);
    for (let d = 1; d <= daysInMonth; d++) {
      const date = new Date(year, month, d);
      const iso = this.toIso(date);
      const counts = countsByDate.get(iso) ?? { bull: 0, bear: 0 };
      days.push({
        iso,
        dayNum: d,
        inRange: date >= rangeStart && date <= rangeEnd,
        isToday: iso === this.toIso(rangeStart),
        bullCount: counts.bull,
        bearCount: counts.bear,
      });
    }
    while (days.length % 7 !== 0) days.push(null);

    const weeks: (CalendarDay | null)[][] = [];
    for (let i = 0; i < days.length; i += 7) weeks.push(days.slice(i, i + 7));

    return { label: monthStart.toLocaleDateString('en-US', { month: 'long', year: 'numeric' }), weeks };
  }

  private toIso(d: Date): string {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }

  selectDay(day: CalendarDay | null): void {
    if (!day || !day.inRange || (day.bullCount === 0 && day.bearCount === 0)) return;
    this.selectedDate = this.selectedDate === day.iso ? null : day.iso;
  }

  clearDateFilter(): void { this.selectedDate = null; }

  getCountdownLabel(daysAway: number): string {
    if (daysAway === 0) return 'Today';
    if (daysAway === 1) return 'Tomorrow';
    return `In ${daysAway} days`;
  }

  getCountdownClass(daysAway: number): string {
    if (daysAway <= 3)  return 'countdown--urgent';
    if (daysAway <= 10) return 'countdown--soon';
    return 'countdown--normal';
  }

  getUrgencyBarWidth(daysAway: number): string {
    const pct = Math.max(0, 100 - (daysAway / this.lookaheadDays) * 100);
    return `${pct}%`;
  }

  async bookmarkTrade(trade: UpcomingTrade): Promise<void> {
    const key = `${trade.symbol}_${trade.period}`;
    try {
      await this.seasonalityService.addToWatchlist(trade);
      this.watchlistedIds.add(key);
      this.messageService.add({
        severity: 'success',
        summary: 'Bookmarked',
        detail: `${trade.symbol} ${trade.period} added to your watchlist.`,
      });
    } catch {
      this.messageService.add({
        severity: 'error',
        summary: 'Error',
        detail: 'Could not save to watchlist.',
      });
    }
  }

  isBookmarked(trade: UpcomingTrade): boolean {
    return this.watchlistedIds.has(`${trade.symbol}_${trade.period}`);
  }

  getWinRate(trade: UpcomingTrade): number {
    if (trade.direction === 'BEAR') {
      return trade.negProb ?? (100 - (trade.posProb ?? 0));
    }
    return trade.posProb ?? 0;
  }

  getWinRateColor(trade: UpcomingTrade): string {
    const rate = this.getWinRate(trade);
    if (trade.direction === 'BEAR') {
      if (rate >= 80) return '#EF4444';
      if (rate >= 65) return '#F97316';
      return '#00C2E8';
    } else {
      if (rate >= 80) return '#22C55E';
      if (rate >= 65) return '#F4B942';
      return '#00C2E8';
    }
  }

  formatDate(isoDate: string | null): string {
    if (!isoDate) return '—';
    const d = new Date(isoDate);
    return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
  }

  formatPct(val: number | null | undefined): string {
    if (val === null || val === undefined) return '—';
    return `${val >= 0 ? '+' : ''}${val.toFixed(2)}%`;
  }

  formatProb(val: number | null | undefined): string {
    if (val === null || val === undefined) return '—';
    return `${val.toFixed(1)}%`;
  }
}
