import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { ChartModule } from 'primeng/chart';
import { ToastModule } from 'primeng/toast';
import { MessageService } from 'primeng/api';
import { Strategy } from '../../../models/strategy.model';
import { MOCK_STRATEGIES } from '../strategies.mock';
import { DeployStrategyDialogComponent, DeployConfig } from '../../../shared/components/deploy-strategy-dialog/deploy-strategy-dialog.component';
import { StatusBadgeComponent } from '../../../shared/components/status-badge/status-badge.component';

@Component({
  selector: 'app-strategy-detail',
  standalone: true,
  imports: [CommonModule, ChartModule, ToastModule, DeployStrategyDialogComponent],
  templateUrl: './strategy-detail.component.html',
  styleUrl: './strategy-detail.component.scss',
  providers: [MessageService]
})
export class StrategyDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private messageService = inject(MessageService);

  strategy: Strategy | null = null;
  isDeployed = false;
  isLoading = true;
  showDeployDialog = false;
  Math = Math;

  // Chart data
  monthlyChartData: any = {};
  equityChartData: any = {};
  monthlyChartOptions: any = {};
  equityChartOptions: any = {};

  ngOnInit() {
    const id = this.route.snapshot.paramMap.get('id');
    setTimeout(() => {
      this.strategy = MOCK_STRATEGIES.find(s => s.id === id) ?? null;
      if (this.strategy) this.buildCharts();
      this.isLoading = false;
    }, 400);
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

  goBack() {
    this.router.navigate(['/strategies']);
  }
}
