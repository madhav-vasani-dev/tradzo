import { Component, Input, OnChanges, SimpleChanges, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TooltipModule } from 'primeng/tooltip';
import { SeasonalityResult, PeriodStats, SeasonalityService } from '../../../core/services/seasonality.service';
import { MessageService } from 'primeng/api';
import { ToastModule } from 'primeng/toast';

interface AnalysisRow {
  period: string;
  stats: PeriodStats;
  direction: 'BULL' | 'BEAR' | 'NEUTRAL';
  streakText: string;
}

@Component({
  selector: 'app-seasonality-analysis-results',
  standalone: true,
  imports: [CommonModule, TooltipModule, ToastModule],
  providers: [MessageService],
  templateUrl: './seasonality-analysis-results.component.html',
  styleUrl: './seasonality-analysis-results.component.scss',
})
export class SeasonalityAnalysisResultsComponent implements OnChanges {
  @Input() result!: SeasonalityResult;
  @Input() probabilityThreshold = 60;
  @Input() benchmarkEnabled = false;
  @Input() confidenceBandsEnabled = false;

  filteredRows: AnalysisRow[] = [];
  expandedPeriod: string | null = null;
  Math = Math;  // expose to template

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['result'] || changes['probabilityThreshold']) {
      this.buildRows();
    }
  }

  private buildRows(): void {
    if (!this.result?.stats) return;

    const rows: AnalysisRow[] = [];

    for (const [period, stats] of Object.entries(this.result.stats)) {
      const posP = stats.posProb ?? stats.pos_prob ?? 0;
      const negP = stats.negProb ?? stats.neg_prob ?? 0;

      const isBull = posP >= this.probabilityThreshold;
      const isBear = negP >= this.probabilityThreshold;

      if (!isBull && !isBear) continue;

      const direction: 'BULL' | 'BEAR' = posP >= negP ? 'BULL' : 'BEAR';

      rows.push({
        period,
        stats,
        direction,
        streakText: this.buildStreakText(stats.streak),
      });
    }

    this.filteredRows = rows.sort((a, b) => this.getWinRate(b) - this.getWinRate(a));
  }

  getWinRate(row: AnalysisRow): number {
    const posP = row.stats.posProb ?? row.stats.pos_prob ?? 0;
    const negP = row.stats.negProb ?? row.stats.neg_prob ?? 0;
    return row.direction === 'BEAR' ? negP : posP;
  }

  private getDirection(stats: PeriodStats): 'BULL' | 'BEAR' | 'NEUTRAL' {
    if ((stats.avg ?? 0) > 0) return 'BULL';
    if ((stats.avg ?? 0) < 0) return 'BEAR';
    return 'NEUTRAL';
  }

  private buildStreakText(streak: number): string {
    if (streak === 0) return '';
    const n = Math.abs(streak);
    const dir = streak > 0 ? 'Bull' : 'Bear';
    return `${n}yr ${dir} Streak`;
  }

  toggleExpand(period: string): void {
    this.expandedPeriod = this.expandedPeriod === period ? null : period;
  }

  getYearValues(period: string): { year: string; value: number | null }[] {
    if (!this.result?.grid) return [];
    return Object.entries(this.result.grid)
      .map(([year, data]) => ({ year, value: data[period] ?? null }))
      .sort((a, b) => Number(a.year) - Number(b.year));
  }

  getProbBarWidth(prob: number | null): string {
    return `${Math.min(prob ?? 0, 100)}%`;
  }

  getProbColor(prob: number | null, direction: string = 'BULL'): string {
    const rate = prob ?? 0;
    if (direction === 'BEAR') {
      if (rate >= 80) return '#EF4444';
      if (rate >= 65) return '#F97316';
      return '#00C2E8';
    } else {
      if (rate >= 80) return '#22C55E';
      if (rate >= 65) return '#F4B942';
      return '#00C2E8';
    }
  }

  formatPct(val: number | null | undefined): string {
    if (val === null || val === undefined) return '—';
    return `${val >= 0 ? '+' : ''}${val.toFixed(2)}%`;
  }

  formatProb(val: number | null | undefined): string {
    if (val === null || val === undefined) return '—';
    return `${val.toFixed(1)}%`;
  }

  get noResults(): boolean {
    return this.filteredRows.length === 0;
  }
}
