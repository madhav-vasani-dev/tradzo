import { Component, inject, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { Subscription } from 'rxjs';

import { SliderModule } from 'primeng/slider';
import { ButtonModule } from 'primeng/button';
import { DatePickerModule } from 'primeng/datepicker';
import { SelectButtonModule } from 'primeng/selectbutton';
import { DropdownModule } from 'primeng/dropdown';
import { TooltipModule } from 'primeng/tooltip';
import { ProgressSpinnerModule } from 'primeng/progressspinner';
import { ToastModule } from 'primeng/toast';
import { MessageService } from 'primeng/api';

import { SeasonalityService, TradeScannerResult } from '../../core/services/seasonality.service';

@Component({
  selector: 'app-trade-scanner',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    SliderModule,
    ButtonModule,
    DatePickerModule,
    SelectButtonModule,
    DropdownModule,
    TooltipModule,
    ProgressSpinnerModule,
    ToastModule,
  ],
  providers: [MessageService],
  templateUrl: './trade-scanner.component.html',
  styleUrl: './trade-scanner.component.scss',
})
export class TradeScannerComponent implements OnDestroy {
  private seasonalityService = inject(SeasonalityService);
  private messageService = inject(MessageService);
  private router = inject(Router);
  private subs = new Subscription();

  // ── State ──────────────────────────────────────────────────────────────────
  isScanning = false;
  hasScanned = false;
  results: TradeScannerResult[] = [];
  error: string | null = null;
  today: Date = new Date();

  // ── Results table search/sort ────────────────────────────────────────────────
  searchQuery = '';
  sortField: keyof TradeScannerResult | null = null;
  sortDir: 1 | -1 = -1;

  get displayedResults(): TradeScannerResult[] {
    let list = this.results;

    const q = this.searchQuery.trim().toUpperCase();
    if (q) {
      list = list.filter(r => r.symbol.includes(q) || (r.displayName ?? '').toUpperCase().includes(q));
    }

    if (this.sortField) {
      const field = this.sortField;
      const dir = this.sortDir;
      list = [...list].sort((a, b) => {
        const av = a[field], bv = b[field];
        if (av === null || av === undefined) return 1;
        if (bv === null || bv === undefined) return -1;
        if (av < bv) return -dir;
        if (av > bv) return dir;
        return 0;
      });
    }

    return list;
  }

  toggleSort(field: keyof TradeScannerResult): void {
    if (this.sortField === field) {
      this.sortDir = this.sortDir === 1 ? -1 : 1;
    } else {
      this.sortField = field;
      this.sortDir = -1;
    }
  }

  sortIcon(field: keyof TradeScannerResult): string {
    if (this.sortField !== field) return 'pi-sort-alt';
    return this.sortDir === 1 ? 'pi-sort-amount-up' : 'pi-sort-amount-down';
  }

  // ── Filters ────────────────────────────────────────────────────────────────
  selectedDate: Date = new Date();
  probabilityThreshold = 60;
  avgReturnThreshold = 0;
  selectedMinYears: string = 'none';
  selectedDirection: 'ALL' | 'BULL' | 'BEAR' = 'ALL';

  // ── Options ────────────────────────────────────────────────────────────────
  directionOptions = [
    { label: 'All', value: 'ALL' },
    { label: 'Bull', value: 'BULL' },
    { label: 'Bear', value: 'BEAR' },
  ];

  minYearsOptions = [
    { label: 'Any', value: 'none' },
    { label: '5+ Yrs', value: '5' },
    { label: '10+ Yrs', value: '10' },
    { label: '15+ Yrs', value: '15' },
    { label: '20+ Yrs', value: '20' },
    { label: '25+ Yrs', value: '25' },
    { label: 'Max', value: 'max' },
  ];

  ngOnDestroy(): void {
    this.subs.unsubscribe();
  }

  // ── Getters ────────────────────────────────────────────────────────────────
  get bullResults(): TradeScannerResult[] {
    return this.results.filter(r => r.direction === 'BULL');
  }

  get bearResults(): TradeScannerResult[] {
    return this.results.filter(r => r.direction === 'BEAR');
  }

  get scanDateLabel(): string {
    return this.selectedDate.toLocaleDateString('en-IN', {
      day: 'numeric', month: 'short', year: 'numeric'
    });
  }

  // ── Actions ────────────────────────────────────────────────────────────────
  scan(): void {
    if (!this.selectedDate) {
      this.messageService.add({ severity: 'warn', summary: 'Date Required', detail: 'Please select a date.' });
      return;
    }
    this.isScanning = true;
    this.error = null;
    this.searchQuery = '';
    const dateStr = this.formatDate(this.selectedDate);
    const minYears = this.selectedMinYears === 'none' ? null : this.selectedMinYears;

    this.subs.add(
      this.seasonalityService.scanTradesByDate(
        dateStr,
        this.probabilityThreshold,
        this.avgReturnThreshold,
        minYears,
        this.selectedDirection,
      ).subscribe({
        next: (results) => {
          this.results = results;
          this.hasScanned = true;
          this.isScanning = false;
        },
        error: (err) => {
          this.error = err?.error?.detail || 'Scan failed. Please try again.';
          this.isScanning = false;
          this.hasScanned = true;
        },
      })
    );
  }

  openInSeasonality(symbol: string): void {
    this.router.navigate(['/seasonality'], { queryParams: { symbol } });
  }

  // ── Helpers ────────────────────────────────────────────────────────────────
  getProbColor(prob: number): string {
    if (prob >= 80) return '#22c55e';
    if (prob >= 70) return '#84cc16';
    if (prob >= 60) return '#eab308';
    return '#94a3b8';
  }

  getAvgReturnColor(avg: number | null): string {
    if (avg === null) return '#94a3b8';
    if (avg > 0) return '#22c55e';
    if (avg < 0) return '#f87171';
    return '#94a3b8';
  }

  getStreakLabel(streak: number | null): string {
    if (streak === null || streak === 0) return '—';
    return streak > 0 ? `+${Math.abs(streak)}` : `${streak}`;
  }

  formatPct(val: number | null): string {
    if (val === null || val === undefined) return '—';
    return val.toFixed(1) + '%';
  }

  private formatDate(d: Date): string {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  }
}
