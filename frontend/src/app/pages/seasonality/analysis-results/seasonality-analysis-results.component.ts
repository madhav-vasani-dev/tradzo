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

interface CalendarCell {
  period: string;
  shortLabel: string;
  avg: number | null;
  winRate: number | null;
  direction: 'BULL' | 'BEAR' | 'NEUTRAL';
  meetsThreshold: boolean;
  bgStyle: string;
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

  // ── Calendar view (alternative to the setup-card list) ──────────────────────
  displayMode: 'list' | 'calendar' = 'list';
  calendarCells: CalendarCell[] = [];
  calendarDailyGroups: { month: string; cells: CalendarCell[] }[] = [];

  private static readonly MONTH_ORDER = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['result'] || changes['probabilityThreshold']) {
      this.buildRows();
      this.buildCalendar();
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

  private buildCalendar(): void {
    if (!this.result?.stats) {
      this.calendarCells = [];
      this.calendarDailyGroups = [];
      return;
    }

    let maxAbsAvg = 0;
    for (const s of Object.values(this.result.stats)) {
      if (s.avg !== null && s.avg !== undefined) maxAbsAvg = Math.max(maxAbsAvg, Math.abs(s.avg));
    }
    if (maxAbsAvg === 0) maxAbsAvg = 5;

    this.calendarCells = (this.result.periodsOrdered || []).map(period => {
      const stats = this.result.stats[period];
      const posP = stats?.posProb ?? stats?.pos_prob ?? 0;
      const negP = stats?.negProb ?? stats?.neg_prob ?? 0;
      const direction: 'BULL' | 'BEAR' | 'NEUTRAL' = !stats ? 'NEUTRAL' : (posP >= negP ? 'BULL' : 'BEAR');
      const winRate = !stats ? null : (direction === 'BEAR' ? negP : posP);
      const avg = stats?.avg ?? null;

      let bgStyle = '';
      if (avg !== null) {
        const alpha = 0.08 + Math.min(Math.abs(avg) / maxAbsAvg, 1) * 0.4;
        bgStyle = avg >= 0 ? `rgba(34,197,94,${alpha.toFixed(2)})` : `rgba(239,68,68,${alpha.toFixed(2)})`;
      }

      return {
        period,
        shortLabel: this.shortLabel(period),
        avg,
        winRate,
        direction,
        meetsThreshold: winRate !== null && winRate >= this.probabilityThreshold,
        bgStyle,
      };
    });

    if (this.result.viewMode === 'daily') {
      const groups = new Map<string, CalendarCell[]>();
      for (const c of this.calendarCells) {
        const month = c.period.split('-')[1] || '?';
        if (!groups.has(month)) groups.set(month, []);
        groups.get(month)!.push(c);
      }
      this.calendarDailyGroups = SeasonalityAnalysisResultsComponent.MONTH_ORDER
        .filter(m => groups.has(m))
        .map(m => ({ month: m, cells: groups.get(m)! }));
    } else {
      this.calendarDailyGroups = [];
    }
  }

  private shortLabel(period: string): string {
    if (this.result.viewMode === 'daily') return period.split('-')[0];
    if (this.result.viewMode === 'weekly') return period.replace('W', '');
    return period;
  }

  cellTooltip(cell: CalendarCell): string {
    if (cell.avg === null) return `${cell.period}: No data`;
    const rateLabel = cell.direction === 'BEAR' ? 'down-rate' : 'up-rate';
    return `${cell.period}: ${this.formatPct(cell.avg)} avg · ${this.formatProb(cell.winRate)} ${rateLabel}`;
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
