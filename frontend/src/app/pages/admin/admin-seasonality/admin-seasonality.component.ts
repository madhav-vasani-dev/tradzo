import { Component, OnInit, OnDestroy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subscription } from 'rxjs';
import { ButtonModule } from 'primeng/button';
import { TableModule } from 'primeng/table';
import { ToastModule } from 'primeng/toast';
import { CheckboxModule } from 'primeng/checkbox';
import { TagModule } from 'primeng/tag';
import { ProgressSpinnerModule } from 'primeng/progressspinner';
import { DialogModule } from 'primeng/dialog';
import { ConfirmDialogModule } from 'primeng/confirmdialog';
import { TooltipModule } from 'primeng/tooltip';
import { MessageService, ConfirmationService } from 'primeng/api';

import {
  SeasonalityService,
  SeasonalityStock,
  AnalysisRunSummary,
  ViewMode,
} from '../../../core/services/seasonality.service';

interface AnalysisProgress {
  running: boolean;
  current: string;
  done: number;
  total: number;
  summary: AnalysisRunSummary | null;
}

@Component({
  selector: 'app-admin-seasonality',
  standalone: true,
  imports: [
    CommonModule, FormsModule,
    ButtonModule, TableModule, ToastModule, CheckboxModule,
    TagModule, ProgressSpinnerModule, DialogModule, ConfirmDialogModule, TooltipModule,
  ],
  providers: [MessageService, ConfirmationService],
  templateUrl: './admin-seasonality.component.html',
  styleUrl: './admin-seasonality.component.scss',
})
export class AdminSeasonalityComponent implements OnInit, OnDestroy {
  private seasonalityService = inject(SeasonalityService);
  private messageService = inject(MessageService);
  private confirmationService = inject(ConfirmationService);
  private subs = new Subscription();

  stocks: SeasonalityStock[] = [];
  isLoadingStocks = true;
  searchQuery = '';
  isSyncingFolder = false;
  isSyncingNifty500 = false;

  get filteredStocks(): SeasonalityStock[] {
    if (!this.searchQuery.trim()) {
      return this.stocks;
    }
    const q = this.searchQuery.trim().toLowerCase();
    return this.stocks.filter(
      (s) =>
        s.symbol.toLowerCase().includes(q) ||
        (s.displayName && s.displayName.toLowerCase().includes(q))
    );
  }

  // Add stock dialog
  showAddDialog = false;
  newSymbol = '';
  newDisplayName = '';
  newDataUrl = '';
  selectedFile: File | null = null;
  isAdding = false;

  // Analysis settings
  selectedModes: ViewMode[] = ['monthly'];
  selectedYearRanges: (number | string)[] = [5, 10];

  viewModeOptions: { label: string; value: ViewMode }[] = [
    { label: 'Monthly', value: 'monthly' },
    { label: 'Weekly', value: 'weekly' },
    { label: 'Daily', value: 'daily' },
  ];

  yearRangeOptions: { label: string; value: number | string }[] = [
    { label: '5 Years', value: 5 },
    { label: '10 Years', value: 10 },
    { label: '15 Years', value: 15 },
    { label: '20 Years', value: 20 },
    { label: '25 Years', value: 25 },
    { label: 'Max', value: 'max' },
  ];

  progress: AnalysisProgress = {
    running: false,
    current: '',
    done: 0,
    total: 0,
    summary: null,
  };

  // Re-upload dialog
  showReuploadDialog = false;
  reuploadSymbol = '';
  reuploadFile: File | null = null;
  reuploadUrl = '';

  ngOnInit(): void {
    this.loadStocks();
  }

  ngOnDestroy(): void {
    this.subs.unsubscribe();
  }

  loadStocks(): void {
    this.isLoadingStocks = true;
    this.subs.add(
      this.seasonalityService.getStocks().subscribe({
        next: (stocks) => {
          this.stocks = stocks;
          this.isLoadingStocks = false;
        },
        error: () => {
          this.isLoadingStocks = false;
          this.messageService.add({ severity: 'error', summary: 'Error', detail: 'Failed to load stocks.' });
        }
      })
    );
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.selectedFile = input.files?.[0] ?? null;
  }

  onReuploadFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.reuploadFile = input.files?.[0] ?? null;
  }

  async addStock(): Promise<void> {
    if (!this.newSymbol.trim()) {
      this.messageService.add({ severity: 'warn', summary: 'Required', detail: 'Please enter a stock symbol.' });
      return;
    }
    if (!this.selectedFile && !this.newDataUrl.trim()) {
      this.messageService.add({ severity: 'warn', summary: 'Required', detail: 'Please provide either a public Google Drive/HTTP link OR select a CSV file.' });
      return;
    }

    this.isAdding = true;
    const sym = this.newSymbol.trim().toUpperCase();
    try {
      if (this.newDataUrl.trim()) {
        await this.seasonalityService.addStock(sym, this.newDisplayName.trim() || sym, this.newDataUrl.trim());
      } else if (this.selectedFile) {
        await this.seasonalityService.uploadStockFile(sym, this.selectedFile);
        if (this.newDisplayName.trim()) {
          await this.seasonalityService.addStock(sym, this.newDisplayName.trim()).catch(() => {});
        }
      }

      this.showAddDialog = false;
      this.newSymbol = '';
      this.newDisplayName = '';
      this.newDataUrl = '';
      this.selectedFile = null;
      this.messageService.add({ severity: 'success', summary: 'Stock Added', detail: `${sym} added successfully.` });
      this.loadStocks();
    } catch (err: any) {
      this.messageService.add({ severity: 'error', summary: 'Failed', detail: err.message || 'Could not add stock.' });
    } finally {
      this.isAdding = false;
    }
  }

  async syncDriveFolder(): Promise<void> {
    this.isSyncingFolder = true;
    try {
      const res = await this.seasonalityService.syncDriveFolder();
      this.messageService.add({
        severity: 'success',
        summary: 'Drive Folder Synced',
        detail: `Found ${res.total_files_found} files. ${res.stocks_added} stocks added, ${res.stocks_updated} updated from Drive folder.`,
        life: 6000,
      });
      this.loadStocks();
    } catch (err: any) {
      this.messageService.add({
        severity: 'error',
        summary: 'Sync Failed',
        detail: err.message || 'Failed to sync Drive folder.',
      });
    } finally {
      this.isSyncingFolder = false;
    }
  }

  async syncNifty500List(): Promise<void> {
    this.isSyncingNifty500 = true;
    try {
      const res = await this.seasonalityService.syncNifty500List();
      this.messageService.add({
        severity: 'success',
        summary: 'Nifty 500 Watchlist Imported',
        detail: `Imported ${res.stocks_added} new stocks, updated ${res.stocks_updated}. Matched ${res.total_drive_files_matched} Drive files.`,
        life: 6000,
      });
      this.loadStocks();
    } catch (err: any) {
      this.messageService.add({
        severity: 'error',
        summary: 'Import Failed',
        detail: err.message || 'Failed to import Nifty 500 list.',
      });
    } finally {
      this.isSyncingNifty500 = false;
    }
  }

  removeStock(symbol: string): void {
    this.confirmationService.confirm({
      header: 'Remove Stock',
      message: `Remove ${symbol}? This will delete the stock and its data file.`,
      icon: 'pi pi-exclamation-triangle',
      acceptLabel: 'Remove',
      rejectLabel: 'Cancel',
      accept: async () => {
        try {
          await this.seasonalityService.removeStock(symbol);
          this.messageService.add({ severity: 'success', summary: 'Removed', detail: `${symbol} has been removed.` });
          this.loadStocks();
        } catch (err: any) {
          this.messageService.add({ severity: 'error', summary: 'Error', detail: err.message });
        }
      },
    });
  }

  isReuploading = false;

  openReupload(symbol: string): void {
    this.reuploadSymbol = symbol;
    this.reuploadFile = null;
    this.reuploadUrl = '';
    this.showReuploadDialog = true;
  }

  async reuploadFile_do(): Promise<void> {
    if (!this.reuploadFile && !this.reuploadUrl.trim()) return;
    this.isReuploading = true;
    try {
      await this.seasonalityService.uploadStockFile(this.reuploadSymbol, this.reuploadFile, this.reuploadUrl.trim() || undefined);
      this.showReuploadDialog = false;
      this.messageService.add({ severity: 'success', summary: 'Updated', detail: `${this.reuploadSymbol} data updated successfully.` });
      this.loadStocks();
    } catch (err: any) {
      this.messageService.add({ severity: 'error', summary: 'Error', detail: err.message || 'Failed to update data file.' });
    } finally {
      this.isReuploading = false;
    }
  }

  toggleMode(mode: ViewMode): void {
    const idx = this.selectedModes.indexOf(mode);
    if (idx === -1) {
      this.selectedModes = [...this.selectedModes, mode];
    } else {
      this.selectedModes = this.selectedModes.filter(m => m !== mode);
    }
  }

  toggleYearRange(yr: number | string): void {
    const idx = this.selectedYearRanges.indexOf(yr);
    if (idx === -1) {
      this.selectedYearRanges = [...this.selectedYearRanges, yr];
    } else {
      this.selectedYearRanges = this.selectedYearRanges.filter(y => y !== yr);
    }
  }

  isYearSelected(yr: number | string): boolean {
    return this.selectedYearRanges.includes(yr);
  }

  isModeSelected(mode: ViewMode): boolean {
    return this.selectedModes.includes(mode);
  }

  get totalCombos(): number {
    return this.stocks.length * this.selectedModes.length * this.selectedYearRanges.length;
  }

  async runAnalysis(): Promise<void> {
    if (this.selectedModes.length === 0 || this.selectedYearRanges.length === 0) {
      this.messageService.add({ severity: 'warn', summary: 'Invalid Config', detail: 'Select at least one mode and one year range.' });
      return;
    }
    if (this.stocks.length === 0) {
      this.messageService.add({ severity: 'warn', summary: 'No Stocks', detail: 'Add stocks before running analysis.' });
      return;
    }

    this.progress = { running: true, current: 'Initializing…', done: 0, total: this.totalCombos, summary: null };

    try {
      const summary = await this.seasonalityService.triggerAnalysis(
        this.selectedModes,
        this.selectedYearRanges,
        (event) => {
          if (event.type === 'start') {
            this.progress = { ...this.progress, total: event.total, current: 'Starting…' };
          } else if (event.type === 'stock_start') {
            this.progress = { ...this.progress, current: `Processing ${event['symbol']}…` };
          } else if (event.type === 'combo') {
            this.progress = { ...this.progress, done: event.done, total: event.total };
          } else if (event.type === 'done') {
            this.progress = { ...this.progress, done: event.done, total: event.total, current: 'Finalizing…' };
          }
        }
      );
      this.progress = { running: false, current: 'Done', done: summary.totalCombos, total: summary.totalCombos, summary };
      this.messageService.add({
        severity: summary.errors > 0 ? 'warn' : 'success',
        summary: 'Analysis Complete',
        detail: `${summary.success} successful, ${summary.errors} errors out of ${summary.totalCombos} combos.`,
        life: 8000,
      });
      this.loadStocks(); // refresh last analysis time
    } catch (err: any) {
      this.progress = { running: false, current: 'Error', done: 0, total: 0, summary: null };
      this.messageService.add({ severity: 'error', summary: 'Analysis Failed', detail: err.message });
    }
  }

  formatFileSize(bytes?: number): string {
    if (!bytes) return '—';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  }

  formatDate(iso?: string): string {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
  }
}
