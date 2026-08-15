import { Component, Input, OnChanges, SimpleChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TooltipModule } from 'primeng/tooltip';
import { ButtonModule } from 'primeng/button';
import { SeasonalityResult, PeriodStats } from '../../../core/services/seasonality.service';

interface GridCell {
  value: number | null;
  colorClass: string;
  bgStyle: string;
  tooltipText: string;
}

@Component({
  selector: 'app-seasonality-data-table',
  standalone: true,
  imports: [CommonModule, TooltipModule, ButtonModule],
  templateUrl: './seasonality-data-table.component.html',
  styleUrl: './seasonality-data-table.component.scss',
})
export class SeasonalityDataTableComponent implements OnChanges {
  @Input() result!: SeasonalityResult;
  @Input() probabilityThreshold = 60;
  @Input() heatMapEnabled = false;
  @Input() confidenceBandsEnabled = false;

  years: string[] = [];
  periods: string[] = [];
  gridData: Record<string, Record<string, GridCell>> = {};
  todayPeriod = '';

  // Max absolute return for heat-map scaling
  private maxReturn = 0;

  private static readonly MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['result'] || changes['heatMapEnabled'] || changes['probabilityThreshold']) {
      this.buildGrid();
      this.todayPeriod = this.computeTodayPeriod();
    }
  }

  /** Current period label in the same format as the backend produces (Jan / W03 / 15-Aug), for the "today" column marker. */
  private computeTodayPeriod(): string {
    if (!this.result) return '';
    const today = new Date();
    const mode = this.result.viewMode;

    if (mode === 'monthly') {
      return SeasonalityDataTableComponent.MONTHS[today.getMonth()];
    }
    if (mode === 'weekly') {
      return `W${String(this.isoWeek(today)).padStart(2, '0')}`;
    }
    const day = String(today.getDate()).padStart(2, '0');
    return `${day}-${SeasonalityDataTableComponent.MONTHS[today.getMonth()]}`;
  }

  /** ISO-8601 week number (matches Python's isocalendar().week used server-side). */
  private isoWeek(date: Date): number {
    const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
    const dayNum = (d.getUTCDay() + 6) % 7;
    d.setUTCDate(d.getUTCDate() - dayNum + 3);
    const firstThursday = new Date(Date.UTC(d.getUTCFullYear(), 0, 4));
    const firstDayNum = (firstThursday.getUTCDay() + 6) % 7;
    firstThursday.setUTCDate(firstThursday.getUTCDate() - firstDayNum + 3);
    return 1 + Math.round((d.getTime() - firstThursday.getTime()) / (7 * 24 * 3600 * 1000));
  }

  isToday(period: string): boolean {
    return !!this.todayPeriod && period === this.todayPeriod;
  }

  private buildGrid(): void {
    if (!this.result) return;

    this.years = (this.result.years_list || Object.keys(this.result.grid)).sort();
    this.periods = this.result.periodsOrdered || [];

    // Find max absolute return for heat-map intensity
    this.maxReturn = 0;
    for (const yr of this.years) {
      for (const p of this.periods) {
        const v = this.result.grid[yr]?.[p];
        if (v !== null && v !== undefined) {
          this.maxReturn = Math.max(this.maxReturn, Math.abs(v));
        }
      }
    }
    if (this.maxReturn === 0) this.maxReturn = 10;

    // Build cell data
    this.gridData = {};
    for (const yr of this.years) {
      this.gridData[yr] = {};
      for (const p of this.periods) {
        const val = this.result.grid[yr]?.[p] ?? null;
        this.gridData[yr][p] = this.makeCell(val);
      }
    }
  }

  private makeCell(value: number | null): GridCell {
    if (value === null) {
      return { value: null, colorClass: 'cell-empty', bgStyle: '', tooltipText: 'No data' };
    }

    const isPositive = value >= 0;
    const intensity = Math.min(Math.abs(value) / this.maxReturn, 1);

    let bgStyle = '';
    let colorClass = '';

    if (this.heatMapEnabled) {
      if (isPositive) {
        const alpha = 0.1 + intensity * 0.55;
        bgStyle = `rgba(34,197,94,${alpha.toFixed(2)})`;
        colorClass = 'cell-positive';
      } else {
        const alpha = 0.1 + intensity * 0.55;
        bgStyle = `rgba(239,68,68,${alpha.toFixed(2)})`;
        colorClass = 'cell-negative';
      }
    } else {
      colorClass = isPositive ? 'cell-positive' : 'cell-negative';
    }

    return {
      value,
      colorClass,
      bgStyle: bgStyle ? `background: ${bgStyle};` : '',
      tooltipText: `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`,
    };
  }

  getStatBgStyle(period: string): string {
    if (!this.heatMapEnabled) return '';
    const stats = this.result.stats[period];
    if (!stats || stats.avg === null) return '';
    return this.makeCell(stats.avg).bgStyle;
  }

  isPeriodHighlighted(period: string): boolean {
    const stats = this.result.stats[period];
    return !!(stats && stats.posProb !== null && stats.posProb >= this.probabilityThreshold);
  }

  getYearTotal(year: string): number | null {
    return this.result.yearTotals?.[year] ?? null;
  }

  getProbClass(period: string): string {
    const stats = this.result.stats[period];
    if (!stats || stats.posProb === null) return '';
    if (stats.posProb >= this.probabilityThreshold) return 'prob-highlight';
    return '';
  }

  getStreakText(period: string): string {
    const s = this.result.stats[period];
    if (!s || s.streak === 0) return '';
    const n = Math.abs(s.streak);
    const dir = s.streak > 0 ? '🟢' : '🔴';
    return `${dir} ${n}yr streak`;
  }

  formatPct(val: number | null | undefined): string {
    if (val === null || val === undefined) return '—';
    return `${val >= 0 ? '+' : ''}${val.toFixed(2)}%`;
  }

  formatProb(val: number | null | undefined): string {
    if (val === null || val === undefined) return '—';
    return `${val.toFixed(1)}%`;
  }

  exportCsv(): void {
    if (!this.result || this.periods.length === 0) return;
    const headers = ['Year', ...this.periods, 'Total Year %'];
    const rows: string[][] = [headers];

    for (const yr of this.years) {
      const row: string[] = [yr];
      for (const p of this.periods) {
        const v = this.result.grid[yr]?.[p];
        row.push(v !== null && v !== undefined ? v.toFixed(2) : '');
      }
      const total = this.getYearTotal(yr);
      row.push(total !== null ? total.toFixed(2) : '');
      rows.push(row);
    }

    // Avg row
    const avgRow = ['Avg'];
    for (const p of this.periods) {
      avgRow.push(this.result.stats[p]?.avg?.toFixed(2) ?? '');
    }
    avgRow.push('');
    rows.push(avgRow);

    const csv = rows.map(r => r.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${this.result.symbol}_${this.result.viewMode}_${this.result.years}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }
}
