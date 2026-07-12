import { Component, OnInit, OnDestroy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Auth, user } from '@angular/fire/auth';
import { Subscription } from 'rxjs';
import { StrategyService } from '../../core/services/strategy.service';
import { UserStrategy, Position } from '../../models/strategy.model';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss'
})
export class DashboardComponent implements OnInit, OnDestroy {
  private auth = inject(Auth);
  private strategyService = inject(StrategyService);

  deployedStrategies: UserStrategy[] = [];
  positions: Position[] = [];
  isLoading = true;

  totalCapital = 0;
  totalLots = 0;
  runningPnl = 0;

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

    // Positions P&L sum
    this.runningPnl = this.positions.reduce((sum, p) => sum + (p.pnl || 0), 0);
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

  async pauseStrategy(id: string) {
    try {
      await this.strategyService.pauseUserStrategy(id);
    } catch (err) {
      console.error('Failed to pause strategy:', err);
    }
  }

  async resumeStrategy(id: string) {
    try {
      await this.strategyService.resumeUserStrategy(id);
    } catch (err) {
      console.error('Failed to resume strategy:', err);
    }
  }

  async stopStrategy(id: string) {
    if (confirm('Are you sure you want to stop this deployment? Open trades will be squared off, and no further orders will be taken.')) {
      try {
        await this.strategyService.stopUserStrategy(id);
      } catch (err) {
        console.error('Failed to stop strategy:', err);
      }
    }
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

  formatINR(val: number): string {
    return `₹${val.toLocaleString('en-IN')}`;
  }
}
