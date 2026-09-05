import { Component, inject, OnInit, OnDestroy } from '@angular/core';
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

import {
  SeasonalityService,
  TradeScannerResult,
  PredefinedScanPreset,
  PredefinedScansResponse,
} from '../../core/services/seasonality.service';

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
export class TradeScannerComponent implements OnInit, OnDestroy {
  private seasonalityService = inject(SeasonalityService);
  private messageService = inject(MessageService);
  private router = inject(Router);
  private subs = new Subscription();

  // ── Scan mode ─────────────────────────────────────────────────────────────
  scanMode: 'predefined' | 'custom' = 'predefined';

  scanModeOptions: Array<{ label: string; value: 'predefined' | 'custom'; icon: string }> = [
    { label: 'Predefined Scans', value: 'predefined', icon: 'pi-bolt' },
    { label: 'Custom Scan',      value: 'custom',     icon: 'pi-sliders-h' },
  ];

  // ── Predefined scan state ─────────────────────────────────────────────────
  predefinedResults: Record<string, TradeScannerResult[]> = {};
  selectedPresetId: string | null = null;
  isLoadingPredefined = false;
  predefinedError: string | null = null;
  predefinedComputedAt: string | null = null;

  /** Metadata for each of the 4 predefined presets — drives card rendering. */
  readonly predefinedPresets: PredefinedScanPreset[] = [
    {
      id: 'open_10',
      label: "Open · 10+ Yrs",
      description: "Today's Open basis, 10+ years of history",
      icon: 'pi-sun',
      returnBasis: 'open',
      minYears: 10,
      probability: 75,
      avgReturn: 1.0,
    },
    {
      id: 'prev_close_10',
      label: 'Prev Close · 10+ Yrs',
      description: 'Prev Close basis, 10+ years of history',
      icon: 'pi-moon',
      returnBasis: 'prev_close',
      minYears: 10,
      probability: 75,
      avgReturn: 1.0,
    },
    {
      id: 'open_5',
      label: "Open · 5+ Yrs",
      description: "Today's Open basis, 5+ years of history",
      icon: 'pi-sun',
      returnBasis: 'open',
      minYears: 5,
      probability: 75,
      avgReturn: 1.0,
    },
    {
      id: 'prev_close_5',
      label: 'Prev Close · 5+ Yrs',
      description: 'Prev Close basis, 5+ years of history',
      icon: 'pi-moon',
      returnBasis: 'prev_close',
      minYears: 5,
      probability: 75,
      avgReturn: 1.0,
    },
  ];

  // ── Custom scan state ─────────────────────────────────────────────────────
  isScanning = false;
  hasScanned = false;
  results: TradeScannerResult[] = [];
  error: string | null = null;

  // ── Shared date picker ────────────────────────────────────────────────────
  selectedDate: Date = new Date();

  // ── Results table search / sort ───────────────────────────────────────────
  searchQuery = '';
  sortField: keyof TradeScannerResult | null = null;
  sortDir: 1 | -1 = -1;

  get activeResults(): TradeScannerResult[] {
    if (this.scanMode === 'predefined' && this.selectedPresetId) {
      return this.predefinedResults[this.selectedPresetId] ?? [];
    }
    return this.results;
  }

  get displayedResults(): TradeScannerResult[] {
    let list = this.activeResults;
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

  // ── Custom scan filters ────────────────────────────────────────────────────
  probabilityThreshold = 60;
  avgReturnThreshold = 0;
  selectedMinYears: string = 'none';
  selectedDirection: 'ALL' | 'BULL' | 'BEAR' = 'ALL';

  directionOptions = [
    { label: 'All', value: 'ALL' },
    { label: 'Bull', value: 'BULL' },
    { label: 'Bear', value: 'BEAR' },
  ];

  returnBasis: 'open' | 'prev_close' = 'open';
  returnBasisOptions = [
    { label: "Today's Open", value: 'open' },
    { label: 'Prev Close', value: 'prev_close' },
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

  // ── Lifecycle ─────────────────────────────────────────────────────────────
  ngOnInit(): void {
    this.loadPredefinedScans();
  }

  ngOnDestroy(): void {
    this.subs.unsubscribe();
  }

  // ── Predefined scan actions ───────────────────────────────────────────────
  loadPredefinedScans(date?: Date): void {
    const d = date ?? this.selectedDate;
    const dateStr = this.formatDate(d);
    this.isLoadingPredefined = true;
    this.predefinedError = null;
    this.predefinedResults = {};
    this.selectedPresetId = null;
    this.searchQuery = '';

    this.subs.add(
      this.seasonalityService.getPredefinedScans(dateStr).subscribe({
        next: (resp: PredefinedScansResponse) => {
          this.predefinedResults = resp.scans;
          this.predefinedComputedAt = resp.computedAt;
          this.isLoadingPredefined = false;
          // Auto-select the first preset
          if (this.predefinedPresets.length > 0) {
            this.selectPreset(this.predefinedPresets[0].id);
          }
        },
        error: (err) => {
          this.predefinedError = err?.error?.detail || 'Failed to load predefined scans.';
          this.isLoadingPredefined = false;
        },
      })
    );
  }

  selectPreset(id: string): void {
    this.selectedPresetId = id;
    this.searchQuery = '';
    this.sortField = null;
  }

  onPredefinedDateChange(): void {
    if (this.scanMode === 'predefined') {
      this.loadPredefinedScans(this.selectedDate);
    }
  }

  onScanModeChange(): void {
    this.searchQuery = '';
    this.sortField = null;
    if (this.scanMode === 'predefined' && Object.keys(this.predefinedResults).length === 0) {
      this.loadPredefinedScans();
    }
  }

  presetResultCount(id: string): number {
    return (this.predefinedResults[id] ?? []).length;
  }

  presetBullCount(id: string): number {
    return (this.predefinedResults[id] ?? []).filter(r => r.direction === 'BULL').length;
  }

  presetBearCount(id: string): number {
    return (this.predefinedResults[id] ?? []).filter(r => r.direction === 'BEAR').length;
  }

  // ── Custom scan actions ───────────────────────────────────────────────────
  scan(): void {
    if (!this.selectedDate) {
      this.messageService.add({ severity: 'warn', summary: 'Date Required', detail: 'Please select a date.' });
      return;
    }
    this.isScanning = true;
    this.error = null;
    this.searchQuery = '';
    this.sortField = null;
    const dateStr = this.formatDate(this.selectedDate);
    const minYears = this.selectedMinYears === 'none' ? null : this.selectedMinYears;

    this.subs.add(
      this.seasonalityService.scanTradesByDate(
        dateStr,
        this.probabilityThreshold,
        this.avgReturnThreshold,
        minYears,
        this.selectedDirection,
        this.returnBasis,
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

  // ── Getters ───────────────────────────────────────────────────────────────
  get bullResults(): TradeScannerResult[] {
    return this.activeResults.filter(r => r.direction === 'BULL');
  }

  get bearResults(): TradeScannerResult[] {
    return this.activeResults.filter(r => r.direction === 'BEAR');
  }

  get scanDateLabel(): string {
    return this.selectedDate.toLocaleDateString('en-IN', {
      day: 'numeric', month: 'short', year: 'numeric'
    });
  }

  get hasResults(): boolean {
    if (this.scanMode === 'predefined') {
      return this.selectedPresetId != null && (this.predefinedResults[this.selectedPresetId]?.length ?? 0) > 0;
    }
    return this.results.length > 0;
  }

  get showResultsTable(): boolean {
    if (this.scanMode === 'predefined') {
      return !this.isLoadingPredefined && this.selectedPresetId != null;
    }
    return !this.isScanning && this.hasScanned && !this.error;
  }

  // ── Helpers ───────────────────────────────────────────────────────────────
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
