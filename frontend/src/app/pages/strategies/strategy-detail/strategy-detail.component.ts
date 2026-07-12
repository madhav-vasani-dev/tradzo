import { Component, OnInit, OnDestroy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { ChartModule } from 'primeng/chart';
import { ToastModule } from 'primeng/toast';
import { MessageService } from 'primeng/api';
import { DialogModule } from 'primeng/dialog';
import { Auth, user } from '@angular/fire/auth';
import { Subscription } from 'rxjs';
import { Strategy, UserStrategy } from '../../../models/strategy.model';
import { StrategyService } from '../../../core/services/strategy.service';
import { DeployStrategyDialogComponent, DeployConfig } from '../../../shared/components/deploy-strategy-dialog/deploy-strategy-dialog.component';

@Component({
  selector: 'app-strategy-detail',
  standalone: true,
  imports: [CommonModule, ChartModule, ToastModule, DialogModule, DeployStrategyDialogComponent],
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
  Math = Math;

  // Dialog confirmation state
  showConfirm = false;
  confirmTitle = '';
  confirmMsg = '';
  confirmBtnText = 'Confirm';
  private actionToExecute: (() => Promise<void>) | null = null;

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
        const d = new Date(e.date);
        return d.toLocaleString('default', { month: 'short' });
      }),
      datasets: [{
        label: 'Portfolio Value ₹',
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

  getRiskClass(): string {
    return this.strategy?.riskLevel.toLowerCase() ?? '';
  }

  formatINR(value: number): string {
    return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(value);
  }

  formatDuration(minutes: number): string {
    if (minutes < 60) return `${minutes}m`;
    if (minutes < 1440) return `${Math.round(minutes / 60)}h`;
    return `${Math.round(minutes / 1440)}d`;
  }

  onDeploy() {
    this.showDeployDialog = true;
  }

  onDeployed(config: DeployConfig) {
    this.isDeployed = true;
    this.messageService.add({
      severity: 'success',
      summary: 'Strategy Deployed!',
      detail: `${config.strategy.name} will go live at 9:15 AM IST on the next market day.`,
      life: 6000
    });
  }

  pauseStrategy() {
    this.confirmTitle = 'Disable Strategy';
    this.confirmMsg = 'Are you sure you want to disable this strategy? It will not execute orders for any future days until you enable it again.';
    this.confirmBtnText = 'Disable';
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
    this.actionToExecute = async () => {
      if (this.deployedUserStrategy) {
        await this.strategyService.disableStrategyForToday(this.deployedUserStrategy.id);
      }
    };
    this.showConfirm = true;
  }

  squareOffToday() {
    this.confirmTitle = 'Square Off & Stop Today';
    this.confirmMsg = 'Are you sure you want to square off all running option positions immediately and stop execution for today?';
    this.confirmBtnText = 'Square Off & Stop';
    this.actionToExecute = async () => {
      if (this.deployedUserStrategy) {
        await this.strategyService.squareOffUserStrategy(this.deployedUserStrategy.id);
      }
    };
    this.showConfirm = true;
  }


  async executeAction() {
    if (this.actionToExecute) {
      try {
        await this.actionToExecute();
        this.messageService.add({
          severity: 'success',
          summary: 'Action Executed',
          detail: 'Strategy deployment status updated successfully.'
        });
      } catch (err: any) {
        console.error('Failed to execute action:', err);
        this.messageService.add({
          severity: 'error',
          summary: 'Action Failed',
          detail: err.message || 'An error occurred.'
        });
      } finally {
        this.actionToExecute = null;
        this.showConfirm = false;
      }
    }
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

  goBack() {
    this.router.navigate(['/strategies']);
  }
}
