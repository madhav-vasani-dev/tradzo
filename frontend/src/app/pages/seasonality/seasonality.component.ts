import { Component, OnInit, OnDestroy, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subscription } from 'rxjs';

// PrimeNG
import { ButtonModule } from 'primeng/button';
import { MultiSelectModule } from 'primeng/multiselect';
import { SelectButtonModule } from 'primeng/selectbutton';
import { SliderModule } from 'primeng/slider';
import { DropdownModule } from 'primeng/dropdown';
import { PanelModule } from 'primeng/panel';
import { AccordionModule } from 'primeng/accordion';
import { ToastModule } from 'primeng/toast';
import { ProgressSpinnerModule } from 'primeng/progressspinner';
import { DialogModule } from 'primeng/dialog';
import { TooltipModule } from 'primeng/tooltip';
import { TagModule } from 'primeng/tag';
import { MessageService } from 'primeng/api';

import {
  SeasonalityService,
  SeasonalityStock,
  SeasonalityResult,
  UpcomingTrade,
  ViewMode,
  YearRange,
  AnalysisFilters,
  UserSeasonalityConfig,
} from '../../core/services/seasonality.service';

import { SeasonalityDataTableComponent } from './data-table/seasonality-data-table.component';
import { SeasonalityAnalysisResultsComponent } from './analysis-results/seasonality-analysis-results.component';
import { SeasonalityUpcomingTradesComponent } from './upcoming-trades/seasonality-upcoming-trades.component';

@Component({
  selector: 'app-seasonality',
  standalone: true,
  imports: [
    CommonModule, FormsModule,
    ButtonModule, MultiSelectModule, SelectButtonModule, SliderModule,
    DropdownModule, PanelModule, AccordionModule, ToastModule,
    ProgressSpinnerModule, DialogModule, TooltipModule, TagModule,
    SeasonalityDataTableComponent,
    SeasonalityAnalysisResultsComponent,
    SeasonalityUpcomingTradesComponent,
  ],
  providers: [MessageService],
  templateUrl: './seasonality.component.html',
  styleUrl: './seasonality.component.scss',
})
export class SeasonalityComponent implements OnInit, OnDestroy {
  private seasonalityService = inject(SeasonalityService);
  private messageService = inject(MessageService);
  private subs = new Subscription();

  // ── Filter state ───────────────────────────────────────────────────────────
  availableStocks: SeasonalityStock[] = [];
  selectedSymbols: string[] = [];
  allStocksSelected = false;

  viewModeOptions = [
    { label: 'Monthly', value: 'monthly' },
    { label: 'Weekly', value: 'weekly' },
    { label: 'Daily', value: 'daily' },
  ];
  selectedViewMode: ViewMode = 'monthly';

  yearOptions = [
    { label: '5Y', value: 5 },
    { label: '10Y', value: 10 },
    { label: '15Y', value: 15 },
    { label: '20Y', value: 20 },
    { label: '25Y', value: 25 },
    { label: 'Max', value: 'max' },
  ];
  selectedYears: YearRange = 10;

  probabilityThreshold = 60;
  lookaheadOptions = [
    { label: '7 days', value: 7 },
    { label: '14 days', value: 14 },
    { label: '30 days', value: 30 },
    { label: '60 days', value: 60 },
    { label: '90 days', value: 90 },
  ];
  lookaheadDays = 30;

  // ── Results state ──────────────────────────────────────────────────────────
  results: SeasonalityResult[] = [];
  upcomingTrades: UpcomingTrade[] = [];
  isLoadingStocks = true;
  isRunning = false;
  hasRunAnalysis = false;

  // ── Saved configs ──────────────────────────────────────────────────────────
  savedConfigs: UserSeasonalityConfig[] = [];
  showSaveDialog = false;
  newConfigName = '';

  // ── UI toggles ─────────────────────────────────────────────────────────────
  heatMapEnabled = false;
  benchmarkEnabled = false;
  confidenceBandsEnabled = false;

  // Section collapse state
  section1Open = true;
  section2Open = true;
  section3Open = true;

  get stockOptions() {
    return this.availableStocks.map(s => ({
      label: `${s.symbol}${s.displayName && s.displayName !== s.symbol ? ' — ' + s.displayName : ''}`,
      value: s.symbol,
    }));
  }

  get hasResults(): boolean { return this.results.length > 0; }
  get hasUpcoming(): boolean { return this.upcomingTrades.length > 0; }

  ngOnInit(): void {
    this.loadStocks();
    this.subs.add(
      this.seasonalityService.getUserConfigs().subscribe({
        next: (configs) => this.savedConfigs = configs,
        error: () => {}
      })
    );
  }

  ngOnDestroy(): void { this.subs.unsubscribe(); }

  private loadStocks(): void {
    this.isLoadingStocks = true;
    this.subs.add(
      this.seasonalityService.getStocks().subscribe({
        next: (stocks) => {
          this.availableStocks = stocks;
          this.isLoadingStocks = false;
        },
        error: (err) => {
          this.isLoadingStocks = false;
          this.messageService.add({ severity: 'error', summary: 'Error', detail: 'Failed to load stock list.' });
        }
      })
    );
  }

  toggleAllStocks(): void {
    this.allStocksSelected = !this.allStocksSelected;
    if (this.allStocksSelected) {
      this.selectedSymbols = this.availableStocks.map(s => s.symbol);
    } else {
      this.selectedSymbols = [];
    }
  }

  onSymbolsChange(): void {
    this.allStocksSelected = this.selectedSymbols.length === this.availableStocks.length;
  }

  runAnalysis(): void {
    if (this.selectedSymbols.length === 0 && !this.allStocksSelected) {
      this.messageService.add({
        severity: 'warn',
        summary: 'No Stocks Selected',
        detail: 'Please select at least one stock or use "Select All".'
      });
      return;
    }

    this.isRunning = true;
    this.results = [];
    this.upcomingTrades = [];

    const symbols = this.allStocksSelected ? [] : this.selectedSymbols;

    // Fetch cached results
    this.subs.add(
      this.seasonalityService.getCachedResults(symbols, this.selectedViewMode, this.selectedYears).subscribe({
        next: (res) => {
          this.results = res;

          // Now fetch upcoming trades
          this.seasonalityService.getUpcomingTrades(
            symbols, this.selectedViewMode, this.selectedYears,
            this.probabilityThreshold, this.lookaheadDays
          ).subscribe({
            next: (trades) => {
              this.upcomingTrades = trades;
              this.isRunning = false;
              this.hasRunAnalysis = true;

              if (res.length === 0) {
                this.messageService.add({
                  severity: 'info',
                  summary: 'No Data Available',
                  detail: 'No OHLCV data found for the selected stock(s). Please verify stock data files in Admin.',
                });
              }
            },
            error: () => { this.isRunning = false; this.hasRunAnalysis = true; }
          });
        },
        error: (err) => {
          this.isRunning = false;
          this.messageService.add({ severity: 'error', summary: 'Error', detail: 'Failed to fetch analysis results.' });
        }
      })
    );
  }

  async saveConfig(): Promise<void> {
    if (!this.newConfigName.trim()) return;
    try {
      await this.seasonalityService.saveUserConfig({
        name: this.newConfigName.trim(),
        symbols: this.selectedSymbols,
        viewMode: this.selectedViewMode,
        years: this.selectedYears,
        probabilityThreshold: this.probabilityThreshold,
        lookaheadDays: this.lookaheadDays,
      });
      this.showSaveDialog = false;
      this.newConfigName = '';
      this.messageService.add({ severity: 'success', summary: 'Saved', detail: 'Analysis config saved.' });
    } catch {
      this.messageService.add({ severity: 'error', summary: 'Error', detail: 'Failed to save config.' });
    }
  }

  loadConfig(config: UserSeasonalityConfig): void {
    this.selectedSymbols = config.symbols;
    this.selectedViewMode = config.viewMode;
    this.selectedYears = config.years;
    this.probabilityThreshold = config.probabilityThreshold;
    this.lookaheadDays = config.lookaheadDays;
    this.messageService.add({ severity: 'info', summary: 'Config Loaded', detail: config.name });
  }

  async deleteConfig(configId: string): Promise<void> {
    try {
      await this.seasonalityService.deleteUserConfig(configId);
      this.messageService.add({ severity: 'success', summary: 'Deleted', detail: 'Config removed.' });
    } catch {
      this.messageService.add({ severity: 'error', summary: 'Error', detail: 'Failed to delete config.' });
    }
  }

  getThresholdLabel(): string {
    return `≥ ${this.probabilityThreshold}%`;
  }

  getProbabilityColor(): string {
    if (this.probabilityThreshold >= 80) return '#22C55E';
    if (this.probabilityThreshold >= 65) return '#F4B942';
    return '#00C2E8';
  }
}
