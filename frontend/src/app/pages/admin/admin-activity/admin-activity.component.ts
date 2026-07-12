import { Component, OnInit, OnDestroy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subscription } from 'rxjs';
import { AdminService } from '../../../core/services/admin.service';
import { AuthService } from '../../../core/services/auth.service';
import { StrategyService } from '../../../core/services/strategy.service';

@Component({
  selector: 'app-admin-activity',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './admin-activity.component.html',
  styleUrl: './admin-activity.component.scss'
})
export class AdminActivityComponent implements OnInit, OnDestroy {
  private adminService = inject(AdminService);
  private authService = inject(AuthService);
  private strategyService = inject(StrategyService);

  selectedDate: string = '';
  logs: any[] = [];
  isLoading = true;
  paperTradingEnabled = true;
  isSuperUser = false;

  private subscriptions = new Subscription();

  // Helper stats
  successRate = '0%';
  totalRan = 0;
  totalFailed = 0;

  ngOnInit() {
    // Set default date to today in Asia/Kolkata (IST)
    const today = new Date();
    // Format to YYYY-MM-DD local timezone
    const offset = today.getTimezoneOffset();
    const localToday = new Date(today.getTime() - (offset * 60 * 1000));
    this.selectedDate = localToday.toISOString().split('T')[0];

    // 1. Subscribe to superuser permissions
    this.subscriptions.add(
      this.authService.isSuperUser$.subscribe(isSuper => {
        this.isSuperUser = isSuper;
      })
    );

    // 2. Subscribe to global paper trading mode settings
    this.subscriptions.add(
      this.strategyService.getTradingMode().subscribe(mode => {
        if (mode) {
          this.paperTradingEnabled = !!mode.paperTrading;
        }
      })
    );

    // 3. Load logs for current date
    this.loadLogs();
  }

  ngOnDestroy() {
    this.subscriptions.unsubscribe();
  }

  loadLogs() {
    this.isLoading = true;

    // Unsubscribe from previous log subscription if any
    const existingLogSub = this.subscriptions.add(
      this.adminService.getActivityLogs(this.selectedDate).subscribe({
        next: (data) => {
          this.logs = data;
          this.calculateStats();
          this.isLoading = false;
        },
        error: (err) => {
          console.error('Error fetching activity logs:', err);
          this.isLoading = false;
        }
      })
    );
  }

  onDateChange() {
    this.loadLogs();
  }

  async toggleTradingMode(newValue: boolean) {
    const user = this.authService.currentUserValue;
    const userUid = user?.uid || 'system';
    const userName = user ? (user.username || user.email) : 'Superuser';

    try {
      this.isLoading = true;
      await this.adminService.toggleTradingMode(newValue, userUid, userName);
      this.paperTradingEnabled = newValue;
    } catch (err) {
      console.error('Failed to toggle trading mode:', err);
      // Revert in UI
      this.paperTradingEnabled = !newValue;
    } finally {
      this.isLoading = false;
    }
  }


  private calculateStats() {
    const orderPlacements = this.logs.filter(l => l.type === 'order_placed');
    const orderFailures = this.logs.filter(l => l.type === 'order_failed' || l.type === 'error');

    this.totalRan = orderPlacements.length + orderFailures.length;
    this.totalFailed = orderFailures.length;

    if (this.totalRan === 0) {
      this.successRate = '—';
    } else {
      const successful = orderPlacements.length;
      this.successRate = `${Math.round((successful / this.totalRan) * 100)}%`;
    }
  }

  // ── UI Helpers ─────────────────────────────────────────────────────────────

  getStatusIcon(severity: string): string {
    const map: Record<string, string> = {
      success: 'pi-check-circle',
      error: 'pi-times-circle',
      warning: 'pi-exclamation-triangle',
      info: 'pi-info-circle'
    };
    return map[severity] ?? 'pi-info-circle';
  }

  getSeverityClass(severity: string): string {
    return `status-${severity.toLowerCase()}`;
  }

  formatTime(createdAt: any): string {
    if (!createdAt) return '—';
    // Firestore Timestamp has toDate()
    if (createdAt.toDate && typeof createdAt.toDate === 'function') {
      return createdAt.toDate().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    }
    const d = new Date(createdAt);
    if (isNaN(d.getTime())) return '—';
    return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }

  formatLogType(type: string): string {
    if (!type) return '';
    return type.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
  }
}

