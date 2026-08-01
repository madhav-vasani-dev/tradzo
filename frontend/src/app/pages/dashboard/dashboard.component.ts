import { Component, OnInit, OnDestroy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ConfirmActionDialogComponent } from '../../shared/components/confirm-action-dialog/confirm-action-dialog.component';
import { Auth, user } from '@angular/fire/auth';
import { Subscription } from 'rxjs';
import { StrategyService } from '../../core/services/strategy.service';
import { UserStrategy, Position } from '../../models/strategy.model';
import { formatMoney, CurrencyCode } from '../../core/format';
import { AuthService } from '../../core/services/auth.service';
import { TradzoUser } from '../../models/user.model';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, FormsModule, ConfirmActionDialogComponent],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss'
})
export class DashboardComponent implements OnInit, OnDestroy {
  private auth = inject(Auth);
  private strategyService = inject(StrategyService);
  authService = inject(AuthService);

  deployedStrategies: UserStrategy[] = [];
  positions: Position[] = [];
  isLoading = true;

  totalCapital = 0;
  totalLots = 0;
  runningPnl = 0;

  // Dialog confirmation state
  showConfirm = false;
  confirmTitle = '';
  confirmMsg = '';
  confirmBtnText = 'Confirm';
  confirmRunningText = 'Processing…';
  actionToExecute: (() => Promise<void>) | null = null;

  get currentUser(): TradzoUser | null {
    return this.authService.currentUserValue;
  }

  get userPaperTrading(): boolean {
    return this.currentUser?.paperTrading !== false;
  }

  async toggleTradingMode(paper: boolean) {
    if (!this.currentUser) return;
    this.confirmTitle = paper ? 'Switch to Simulation Mode' : 'Switch to Live Orders Mode';
    this.confirmMsg = paper 
      ? 'Are you sure you want to switch your account to Simulation Mode? All future entry orders placed by the system on your deployments will be paper trades.'
      : 'Are you sure you want to switch your account to Live Orders Mode? All future entry orders placed by the system on your deployments will execute real trades on your connected broker account.';
    this.confirmBtnText = paper ? 'Switch to Simulation' : 'Switch to Live';
    this.confirmRunningText = 'Switching…';
    this.actionToExecute = async () => {
      await this.authService.toggleUserTradingMode(this.currentUser!.uid, !paper);
    };
    this.showConfirm = true;
  }

  private subscriptions = new Subscription();

  ngOnInit(): void {
    this.subscriptions.add(
      user(this.auth).subscribe((u) => {
        if (u) {
          this.loadUserDashboardData(u.uid);
        } else {
          this.resetData();
        }
      })
    );
  }

  ngOnDestroy(): void {
    this.subscriptions.unsubscribe();
  }

  private loadUserDashboardData(userId: string) {
    this.isLoading = true;

    // 1. Subscribe to user strategy deployments
    this.subscriptions.add(
      this.strategyService.getUserStrategies(userId).subscribe({
        next: (deployments) => {
          // Filter out stopped ones to keep dashboard clean
          this.deployedStrategies = deployments.filter((d) => d.status !== 'stopped');
          this.calculateStats();
        },
        error: (err) => {
          console.error('Error fetching deployed strategies:', err);
          this.isLoading = false;
        }
      })
    );

    // 2. Subscribe to active positions for today
    this.subscriptions.add(
      this.strategyService.getUserPositions(userId).subscribe({
        next: (userPositions) => {
          this.positions = userPositions;
          this.calculateStats();
          this.isLoading = false;
        },
        error: (err) => {
          console.error('Error fetching user positions:', err);
          this.isLoading = false;
        }
      })
    );
  }

  private calculateStats() {
    this.totalCapital = this.deployedStrategies.reduce((sum, d) => sum + (d.deployedAmount || 0), 0);
    this.totalLots = this.deployedStrategies.reduce((sum, d) => sum + (d.multiplier || 0), 0);

    // Positions P&L sum — prefer the INR-equivalent so mixed-settlement positions add up in one currency.
    this.runningPnl = this.positions.reduce((sum, p) => sum + this.effectivePnl(p, true), 0);
  }

  private resetData() {
    this.deployedStrategies = [];
    this.positions = [];
    this.totalCapital = 0;
    this.totalLots = 0;
    this.runningPnl = 0;
    this.isLoading = false;
  }

  // ── Strategy Actions ───────────────────────────────────────────────────────

  pauseStrategy(id: string) {
    this.confirmTitle = 'Disable Strategy';
    this.confirmMsg = 'Are you sure you want to disable this strategy? It will not execute orders for any future days until you enable it again.';
    this.confirmBtnText = 'Disable';
    this.confirmRunningText = 'Disabling…';
    this.actionToExecute = async () => {
      await this.strategyService.pauseUserStrategy(id);
    };
    this.showConfirm = true;
  }

  resumeStrategy(id: string) {
    this.confirmTitle = 'Enable Strategy';
    this.confirmMsg = 'Are you sure you want to enable this strategy? It will start executing orders automatically on future trading days.';
    this.confirmBtnText = 'Enable';
    this.confirmRunningText = 'Enabling…';
    this.actionToExecute = async () => {
      await this.strategyService.resumeUserStrategy(id);
    };
    this.showConfirm = true;
  }


  onActionSucceeded() {
    this.actionToExecute = null;
  }

  onActionFailed(err: Error) {
    this.actionToExecute = null;
    console.error('Failed to execute action:', err);
  }


  // ── UI Helpers ─────────────────────────────────────────────────────────────

  getStatusLabel(status: string): string {
    const labels: Record<string, string> = {
      enabled: 'Enabled',
      ready: 'Ready for Entry',
      trade_active: 'Trade Active',
      trade_closed: 'Trade Closed',
      paused: 'Paused',
      stopped: 'Stopped'
    };
    return labels[status] || status.toUpperCase();
  }

  getStatusClass(status: string): string {
    return `status-${status.toLowerCase()}`;
  }

  getPnlClass(pnl: number | null): string {
    if (!pnl) return 'pnl-neutral';
    return pnl > 0 ? 'pnl-positive' : 'pnl-negative';
  }

  /**
   * P&L to show for a position: the booked `pnl` once it closes, otherwise the live
   * mark-to-market the feed writes while it is open.
   * `preferInr` picks the INR equivalent so mixed-settlement positions can be summed.
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

  /** Currency shared by the user's deployments, or INR when mixed/absent. */
  get portfolioCurrency(): CurrencyCode {
    const currencies = new Set(this.deployedStrategies.map(d => d.currency).filter(Boolean));
    return currencies.size === 1 ? [...currencies][0]! : 'INR';
  }

  formatMoney(value: number | null | undefined, currency?: CurrencyCode): string {
    return formatMoney(value, currency);
  }

  /** A position price, preferring the INR-equivalent field when present (prices need decimals). */
  posPrice(pos: any, base: string): string {
    const inr = pos?.[`${base}Inr`];
    if (inr !== undefined && inr !== null) return formatMoney(inr, 'INR', { decimals: 2 });
    return formatMoney(pos?.[base], pos?.currency, { decimals: 2 });
  }

  /** A position PnL (booked, or live while open), preferring the INR-equivalent field. */
  posPnl(pos: any): string {
    const hasInr = pos?.pnlInr != null || pos?.unrealizedPnlInr != null;
    if (hasInr) return formatMoney(this.effectivePnl(pos, true), 'INR');
    return formatMoney(this.effectivePnl(pos), pos?.currency);
  }
}
