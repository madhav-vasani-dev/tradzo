import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';
import { StrategyService } from '../../core/services/strategy.service';
import { AdminService } from '../../core/services/admin.service';
import { formatMoney, formatDate, CurrencyCode } from '../../core/format';

@Component({
  selector: 'app-pnl',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './pnl.component.html',
  styleUrl: './pnl.component.scss'
})
export class PnlComponent implements OnInit {
  private authService = inject(AuthService);
  private strategyService = inject(StrategyService);
  private adminService = inject(AdminService);
  private router = inject(Router);

  // Filter state
  startDate = '';
  endDate = '';
  selectedStrategy = '';
  selectedUser = '';

  // Options lists
  deployedStrategies: any[] = [];
  allUsers: any[] = [];
  isAdmin = false;
  currentUserId = '';

  // P&L data
  positions: any[] = [];
  isLoading = false;
  errorMsg = '';

  // Metrics
  totalTrades = 0;
  winningTrades = 0;
  losingTrades = 0;
  netPnl = 0;
  winRate = 0;
  totalProfit = 0;
  totalLoss = 0;

  ngOnInit() {
    const user = this.authService.currentUserValue;
    if (!user) {
      this.router.navigate(['/auth']);
      return;
    }

    this.currentUserId = user.uid;
    this.selectedUser = user.uid;
    this.isAdmin = this.authService.isAdmin;

    // Set default dates (past 30 days)
    const today = new Date();
    const pastDate = new Date();
    pastDate.setDate(today.getDate() - 30);

    const offset = today.getTimezoneOffset();
    const localToday = new Date(today.getTime() - (offset * 60 * 1000));
    const localPast = new Date(pastDate.getTime() - (offset * 60 * 1000));

    this.endDate = localToday.toISOString().split('T')[0];
    this.startDate = localPast.toISOString().split('T')[0];

    // Load filter options
    this.loadFilterOptions();
    
    // Load default report
    this.loadReport();
  }

  async loadFilterOptions() {
    try {
      // 1. Get strategies deployed by this user
      this.strategyService.getUserStrategies(this.currentUserId).subscribe(strategies => {
        // Dedup strategies by strategyId
        const seen = new Set();
        this.deployedStrategies = strategies.filter(s => {
          const duplicate = seen.has(s.strategyId);
          seen.add(s.strategyId);
          return !duplicate;
        });
      });

      // 2. If admin, load all users to filter by user
      if (this.isAdmin) {
        this.adminService.getAllUsers().subscribe(users => {
          this.allUsers = users;
        });
      }
    } catch (err) {
      console.error('Failed to load filter options:', err);
    }
  }

  async loadReport() {
    this.isLoading = true;
    this.errorMsg = '';
    
    try {
      const data = await this.strategyService.getPnlReport(
        this.selectedUser,
        this.selectedStrategy || undefined,
        this.startDate || undefined,
        this.endDate || undefined
      );

      this.positions = data.positions || [];
      this.calculateMetrics();
    } catch (err: any) {
      this.errorMsg = err.message || 'Failed to load report data.';
    } finally {
      this.isLoading = false;
    }
  }

  private calculateMetrics() {
    this.totalTrades = this.positions.length;
    this.winningTrades = 0;
    this.losingTrades = 0;
    this.netPnl = 0;
    this.totalProfit = 0;
    this.totalLoss = 0;

    for (const pos of this.positions) {
      const pnl = this.effectivePnl(pos, true);
      this.netPnl += pnl;

      if (pnl > 0) {
        this.winningTrades++;
        this.totalProfit += pnl;
      } else if (pnl < 0) {
        this.losingTrades++;
        this.totalLoss += Math.abs(pnl);
      }
    }

    this.winRate = this.totalTrades > 0 ? Math.round((this.winningTrades / this.totalTrades) * 100) : 0;
  }

  // Exports

  exportCSV() {
    if (this.positions.length === 0) return;

    const headers = ['Date', 'Symbol', 'Broker', 'Type', 'Strike', 'Entry Price', 'Exit Price', 'Qty', 'P&L'];
    const rows = this.positions.map((p: any) => [
      p.date,
      p.symbol,
      p.broker.toUpperCase(),
      p.optionType,
      p.strike,
      p.entryPriceInr ?? p.entryPrice,
      (p.exitPriceInr ?? p.exitPrice) ?? '—',
      p.quantity,
      this.hasPnl(p) ? this.effectivePnl(p, true) : '—'
    ]);

    const csvContent = [
      headers.join(','),
      ...rows.map(e => e.map(val => `"${val}"`).join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `Tradzo_PnL_Report_${this.startDate}_to_${this.endDate}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  exportPDF() {
    // Standard window.print() will use the custom CSS print layout
    window.print();
  }

  // Formatting helpers

  /**
   * Display currency for the report. Each position shows its INR-equivalent when available,
   * so the report is INR unless every position is a single non-INR currency with no INR value.
   */
  get reportCurrency(): CurrencyCode {
    const displayed = new Set(
      this.positions.map((p: any) => (p.pnlInr !== undefined && p.pnlInr !== null ? 'INR' : (p.currency || 'INR')))
    );
    return displayed.size === 1 ? [...displayed][0] : 'INR';
  }

  formatMoney(value: number | null | undefined, currency?: CurrencyCode): string {
    return formatMoney(value, currency, { decimals: 2 });
  }

  /** A position price, preferring the INR-equivalent field when present. */
  posPrice(pos: any, base: string): string {
    const inr = pos?.[`${base}Inr`];
    if (inr !== undefined && inr !== null) return formatMoney(inr, 'INR', { decimals: 2 });
    return formatMoney(pos?.[base], pos?.currency, { decimals: 2 });
  }

  /** True when the position has any P&L to report — booked, or live while it is open. */
  hasPnl(pos: any): boolean {
    return pos?.pnl != null || pos?.pnlInr != null
        || pos?.unrealizedPnl != null || pos?.unrealizedPnlInr != null;
  }

  /**
   * P&L for a position: the booked `pnl` once it closes, otherwise the live
   * mark-to-market written while it is open.
   * `preferInr` picks the INR equivalent so mixed-settlement rows total in one currency.
   */
  effectivePnl(pos: any, preferInr = false): number {
    const pick = (base: string) => {
      const inr = pos?.[`${base}Inr`];
      if (preferInr && inr !== undefined && inr !== null) return inr;
      return pos?.[base];
    };
    const booked = pick('pnl');
    if (booked !== undefined && booked !== null) return booked;
    return pick('unrealizedPnl') ?? 0;
  }

  /** A position PnL (booked, or live while open), preferring the INR-equivalent field. */
  posPnl(pos: any): string {
    if (!this.hasPnl(pos)) return formatMoney(null, pos?.currency, { decimals: 2 });
    const hasInr = pos?.pnlInr != null || pos?.unrealizedPnlInr != null;
    if (hasInr) return formatMoney(this.effectivePnl(pos, true), 'INR', { decimals: 2 });
    return formatMoney(this.effectivePnl(pos), pos?.currency, { decimals: 2 });
  }

  formatDate(dateStr: string): string {
    return formatDate(dateStr);
  }

  getPnlClass(pnl: number): string {
    if (pnl > 0) return 'text-green';
    if (pnl < 0) return 'text-red';
    return '';
  }
}
