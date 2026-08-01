import { Component, OnInit, OnDestroy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { ChartModule } from 'primeng/chart';
import { ToastModule } from 'primeng/toast';
import { MessageService } from 'primeng/api';
import { Auth, user } from '@angular/fire/auth';
import { Subscription } from 'rxjs';
import { Strategy, UserStrategy } from '../../../models/strategy.model';
import { StrategyService } from '../../../core/services/strategy.service';
import { DeployStrategyDialogComponent, DeployConfig } from '../../../shared/components/deploy-strategy-dialog/deploy-strategy-dialog.component';
import { ConfirmActionDialogComponent } from '../../../shared/components/confirm-action-dialog/confirm-action-dialog.component';
import { formatMoney as fmtMoney, formatDate as fmtDate, currencySymbol, CurrencyCode } from '../../../core/format';

@Component({
  selector: 'app-strategy-detail',
  standalone: true,
  imports: [CommonModule, ChartModule, ToastModule, DeployStrategyDialogComponent, ConfirmActionDialogComponent],
  templateUrl: './strategy-detail.component.html',
  styleUrl: './strategy-detail.component.scss',
  providers: [MessageService]
})
export class StrategyDetailComponent implements OnInit, OnDestroy {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private auth = inject(Auth);
  private strategyService = inject(StrategyService);
  private messageService = inject(MessageService);

  strategy: Strategy | null = null;
  isDeployed = false;
  deployedUserStrategy: UserStrategy | null = null;
  isLoading = true;
  showDeployDialog = false;
  /** True while the deployment write is in flight — keeps the Deploy button from firing twice. */
  isDeploying = false;
  Math = Math;

  // Dialog confirmation state. The dialog runs `actionToExecute` itself and blocks
  // repeat clicks while it is in flight.
  showConfirm = false;
  confirmTitle = '';
  confirmMsg = '';
  confirmBtnText = 'Confirm';
  confirmRunningText = 'Processing…';
  actionToExecute: (() => Promise<void>) | null = null;

  // Chart data
  monthlyChartData: any = {};
  equityChartData: any = {};
  monthlyChartOptions: any = {};
  equityChartOptions: any = {};

  private sub = new Subscription();

  ngOnInit() {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      // 1. Fetch strategy config
      this.sub.add(
        this.strategyService.getStrategy(id).subscribe({
          next: (strat) => {
            this.strategy = strat;
            if (this.strategy) {
              this.buildCharts();
            }
            this.isLoading = false;
          },
          error: (err) => {
            console.error('Error loading strategy:', err);
            this.isLoading = false;
          }
        })
      );

      // 2. Fetch user strategy deployment state
      this.sub.add(
        user(this.auth).subscribe((u) => {
          if (u) {
            this.sub.add(
              this.strategyService.getUserStrategies(u.uid).subscribe((userStrats) => {
                const found = userStrats.find(us => us.strategyId === id && us.status !== 'stopped');
                this.deployedUserStrategy = found ?? null;
                this.isDeployed = !!found;
              })
            );
          } else {
            this.deployedUserStrategy = null;
            this.isDeployed = false;
          }
        })
      );
    } else {
      this.isLoading = false;
    }
  }

  ngOnDestroy() {
    this.sub.unsubscribe();
  }



  private buildCharts() {
    if (!this.strategy) return;
    const p = this.strategy.performance;
    const gridColor = 'rgba(255,255,255,0.06)';
    const textColor = '#8B95B0';

    const colors = p.monthlyReturns.map(m => m.returnPct >= 0 ? 'rgba(34,197,94,0.75)' : 'rgba(239,68,68,0.75)');
    const borderColors = p.monthlyReturns.map(m => m.returnPct >= 0 ? '#22C55E' : '#EF4444');

    this.monthlyChartData = {
      labels: p.monthlyReturns.map(m => m.month.split(' ')[0]),
      datasets: [{
        label: 'Monthly Return %',
        data: p.monthlyReturns.map(m => m.returnPct),
        backgroundColor: colors,
        borderColor: borderColors,
        borderWidth: 1,
        borderRadius: 4,
      }]
    };

    this.equityChartData = {
      labels: p.equityCurve.map(e => {
        if (!e.date) return '';
        const parts = e.date.split('-');
        if (parts.length === 3) {
          const yr = parts[0].slice(2);
          const mIdx = parseInt(parts[1], 10) - 1;
          const monthNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
          return `${monthNames[mIdx] || ''} '${yr}`;
        }
        return e.date;
      }),
      datasets: [{
        label: `Portfolio Value ${currencySymbol(this.strategy?.currency)}`,
        data: p.equityCurve.map(e => e.value),
        borderColor: '#00C2E8',
        backgroundColor: 'rgba(0,194,232,0.08)',
        borderWidth: 2,
        pointRadius: 3,
        pointBackgroundColor: '#00C2E8',
        fill: true,
        tension: 0.4,
      }]
    };

    const baseOptions = {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#0D1526',
          borderColor: 'rgba(255,255,255,0.1)',
          borderWidth: 1,
          titleColor: '#F0F4FF',
          bodyColor: '#8B95B0',
          padding: 12,
          cornerRadius: 8,
        }
      },
      scales: {
        x: { grid: { color: gridColor }, ticks: { color: textColor, font: { size: 11 } } },
        y: { grid: { color: gridColor }, ticks: { color: textColor, font: { size: 11 } } }
      }
    };

    this.monthlyChartOptions = { ...baseOptions };
    this.equityChartOptions = { ...baseOptions };
  }

  get startingCapital(): number {
    return this.strategy?.performance?.equityCurve?.[0]?.value ?? this.strategy?.minimumAmount ?? 0;
  }

  getRiskClass(): string {
    return this.strategy?.riskLevel.toLowerCase() ?? '';
  }

  /** Format money in the strategy's currency (or an explicit override). */
  formatMoney(value: number, currency?: CurrencyCode): string {
    return fmtMoney(value, currency ?? this.strategy?.currency);
  }

  formatDuration(minutes: number): string {
    if (minutes < 60) return `${minutes}m`;
    if (minutes < 1440) return `${Math.round(minutes / 60)}h`;
    return `${Math.round(minutes / 1440)}d`;
  }

  onDeploy() {
    if (this.isDeploying) return;
    this.showDeployDialog = true;
  }

  async onDeployed(config: DeployConfig) {
    if (this.isDeploying) return;
    const currentUser = this.auth.currentUser;
    if (!currentUser) {
      this.messageService.add({
        severity: 'error',
        summary: 'Not Authenticated',
        detail: 'Please log in to deploy strategies.'
      });
      return;
    }

    this.isDeploying = true;
    try {
      await this.strategyService.deployStrategy(
        currentUser.uid,
        config.strategy.id,
        config.strategyCode,
        config.strategy.name,
        config.brokerAccountId,
        config.brokerName,
        config.deployedAmount,
        config.multiplier
      );

      this.isDeployed = true;
      this.messageService.add({
        severity: 'success',
        summary: 'Strategy Deployed!',
        detail: `${config.strategy.name} deployed successfully with ${config.multiplier}x lot multiplier.`,
        life: 6000
      });
    } catch (err: any) {
      console.error('Error deploying strategy:', err);
      this.messageService.add({
        severity: 'error',
        summary: 'Deployment Failed',
        detail: err.message || 'Failed to deploy strategy.'
      });
    } finally {
      this.isDeploying = false;
    }
  }

  pauseStrategy() {
    this.confirmTitle = 'Disable Strategy';
    this.confirmMsg = 'Are you sure you want to disable this strategy? It will not execute orders for any future days until you enable it again.';
    this.confirmBtnText = 'Disable';
    this.confirmRunningText = 'Disabling…';
    this.actionToExecute = async () => {
      if (this.deployedUserStrategy) {
        await this.strategyService.pauseUserStrategy(this.deployedUserStrategy.id);
      }
    };
    this.showConfirm = true;
  }

  resumeStrategy() {
    this.confirmTitle = 'Activate Strategy';
    this.confirmMsg = 'Are you sure you want to activate this strategy? It will start executing orders automatically on future trading days.';
    this.confirmBtnText = 'Activate';
    this.confirmRunningText = 'Activating…';
    this.actionToExecute = async () => {
      if (this.deployedUserStrategy) {
        await this.strategyService.resumeUserStrategy(this.deployedUserStrategy.id);
      }
    };
    this.showConfirm = true;
  }

  stopTodayOnly() {
    this.confirmTitle = 'Stop Algo for Today';
    this.confirmMsg = 'Are you sure you want to stop the algorithm for today only? No entry orders will be taken today. It will resume automatically tomorrow.';
    this.confirmBtnText = 'Stop for Today';
    this.confirmRunningText = 'Stopping…';
    this.actionToExecute = async () => {
      if (this.deployedUserStrategy) {
        await this.strategyService.disableStrategyForToday(this.deployedUserStrategy.id);
      }
    };
    this.showConfirm = true;
  }

  squareOffToday() {
    this.confirmTitle = 'Square Off & Stop Today';
    this.confirmMsg = 'Are you sure you want to square off all running positions immediately and stop execution for today?';
    this.confirmBtnText = 'Square Off & Stop';
    this.confirmRunningText = 'Squaring off…';
    this.actionToExecute = async () => {
      if (this.deployedUserStrategy) {
        await this.strategyService.squareOffUserStrategy(this.deployedUserStrategy.id);
      }
    };
    this.showConfirm = true;
  }


  onActionSucceeded() {
    this.actionToExecute = null;
    this.messageService.add({
      severity: 'success',
      summary: 'Action Executed',
      detail: 'Strategy deployment status updated successfully.'
    });
  }

  onActionFailed(err: Error) {
    this.actionToExecute = null;
    console.error('Failed to execute action:', err);
    this.messageService.add({
      severity: 'error',
      summary: 'Action Failed',
      detail: err.message || 'An error occurred.'
    });
  }

  getStatusLabel(status: string): string {
    const labels: Record<string, string> = {
      enabled: 'Enabled',
      ready: 'Ready for Entry',
      trade_active: 'Trade Active',
      trade_closed: 'Trade Closed',
      paused: 'Paused',
      disabled_today: 'Stopped for Today',
      stopped: 'Stopped'
    };
    return labels[status] || status.toUpperCase();
  }

  getStatusClass(status: string): string {
    return `status-${status.toLowerCase()}`;
  }

  formatDate(dateStr: string): string {
    return fmtDate(dateStr);
  }

  goBack() {
    this.router.navigate(['/strategies']);
  }
}
