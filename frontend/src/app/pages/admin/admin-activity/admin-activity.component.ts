import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';

interface ActivityLog {
  id: string;
  date: string;
  time: string;
  event: string;
  status: 'success' | 'failed' | 'warning' | 'info';
  strategiesRan: number;
  strategiesFailed: number;
  details: string;
}

// Phase 1: Mock activity data — Phase 2 will read from Firestore/backend logs
const MOCK_ACTIVITY: ActivityLog[] = [
  { id: '1', date: '2026-07-05', time: '09:15:03', event: 'Morning Execution', status: 'success', strategiesRan: 4, strategiesFailed: 0, details: 'All 4 active strategies executed successfully at market open.' },
  { id: '2', date: '2026-07-04', time: '09:15:01', event: 'Morning Execution', status: 'warning', strategiesRan: 4, strategiesFailed: 1, details: '1 strategy (Iron Condor Pro) failed due to insufficient margin.' },
  { id: '3', date: '2026-07-03', time: '09:15:08', event: 'Morning Execution', status: 'success', strategiesRan: 3, strategiesFailed: 0, details: 'All strategies executed. Market gapped up 0.4%.' },
  { id: '4', date: '2026-07-02', time: '09:15:02', event: 'Morning Execution', status: 'failed', strategiesRan: 0, strategiesFailed: 3, details: 'Backend connection to Upstox API timed out. No orders were placed.' },
  { id: '5', date: '2026-07-01', time: '09:15:00', event: 'Morning Execution', status: 'success', strategiesRan: 3, strategiesFailed: 0, details: 'All strategies executed successfully.' },
  { id: '6', date: '2026-06-30', time: '14:32:17', event: 'Token Refresh', status: 'success', strategiesRan: 0, strategiesFailed: 0, details: 'Upstox access tokens refreshed for 2 users successfully.' },
  { id: '7', date: '2026-06-29', time: '09:15:05', event: 'Morning Execution', status: 'success', strategiesRan: 3, strategiesFailed: 0, details: '3 strategies executed.' },
];

@Component({
  selector: 'app-admin-activity',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './admin-activity.component.html',
  styleUrl: './admin-activity.component.scss'
})
export class AdminActivityComponent implements OnInit {
  logs = MOCK_ACTIVITY;
  isLoading = false;

  get successRate(): string {
    const executions = this.logs.filter(l => l.event === 'Morning Execution');
    if (!executions.length) return '—';
    const success = executions.filter(l => l.status === 'success').length;
    return `${Math.round((success / executions.length) * 100)}%`;
  }

  get totalRan(): number { return this.logs.reduce((s, l) => s + l.strategiesRan, 0); }
  get totalFailed(): number { return this.logs.reduce((s, l) => s + l.strategiesFailed, 0); }

  ngOnInit() {}

  getStatusIcon(status: string): string {
    const map: Record<string, string> = {
      success: 'pi-check-circle',
      failed: 'pi-times-circle',
      warning: 'pi-exclamation-triangle',
      info: 'pi-info-circle'
    };
    return map[status] ?? 'pi-info-circle';
  }
}
