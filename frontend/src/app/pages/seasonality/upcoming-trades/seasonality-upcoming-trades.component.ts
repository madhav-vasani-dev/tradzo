import { Component, Input, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TooltipModule } from 'primeng/tooltip';
import { ToastModule } from 'primeng/toast';
import { MessageService } from 'primeng/api';
import { UpcomingTrade, SeasonalityService } from '../../../core/services/seasonality.service';

@Component({
  selector: 'app-seasonality-upcoming-trades',
  standalone: true,
  imports: [CommonModule, TooltipModule, ToastModule],
  providers: [MessageService],
  templateUrl: './seasonality-upcoming-trades.component.html',
  styleUrl: './seasonality-upcoming-trades.component.scss',
})
export class SeasonalityUpcomingTradesComponent {
  @Input() trades: UpcomingTrade[] = [];
  @Input() lookaheadDays = 30;

  private seasonalityService = inject(SeasonalityService);
  private messageService = inject(MessageService);

  watchlistedIds = new Set<string>();

  get groupedTrades(): { symbol: string; trades: UpcomingTrade[] }[] {
    const map = new Map<string, UpcomingTrade[]>();
    for (const t of this.trades) {
      if (!map.has(t.symbol)) map.set(t.symbol, []);
      map.get(t.symbol)!.push(t);
    }
    return Array.from(map.entries()).map(([symbol, trades]) => ({ symbol, trades }));
  }

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
