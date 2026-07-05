import { Component, OnInit, OnDestroy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, ActivatedRoute } from '@angular/router';
import { ToastModule } from 'primeng/toast';
import { MessageService } from 'primeng/api';
import { Subscription, combineLatest } from 'rxjs';
import { AdminService } from '../../../core/services/admin.service';
import { StrategyService } from '../../../core/services/strategy.service';
import { TradzoUser } from '../../../models/user.model';
import { UserStrategy } from '../../../models/strategy.model';

@Component({
  selector: 'app-admin-user-detail',
  standalone: true,
  imports: [CommonModule, ToastModule],
  templateUrl: './admin-user-detail.component.html',
  styleUrl: './admin-user-detail.component.scss',
  providers: [MessageService]
})
export class AdminUserDetailComponent implements OnInit, OnDestroy {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private adminService = inject(AdminService);
  private strategyService = inject(StrategyService);
  private messageService = inject(MessageService);

  user: TradzoUser | null = null;
  userStrategies: UserStrategy[] = [];
  isLoading = true;
  actionLoading: string | null = null;

  private subs: Subscription[] = [];

  ngOnInit() {
    const uid = this.route.snapshot.paramMap.get('uid')!;
    const userSub = this.adminService.getUser(uid).subscribe(u => { this.user = u; });
    const strategySub = this.strategyService.getUserStrategies(uid).subscribe(s => {
      this.userStrategies = s;
      this.isLoading = false;
    });
    this.subs.push(userSub, strategySub);
  }

  ngOnDestroy() { this.subs.forEach(s => s.unsubscribe()); }

  async toggleAdmin() {
    if (!this.user || this.user.isSuperUser) return;
    await this.adminService.setAdminRole(this.user.uid, !this.user.isAdmin);
    this.messageService.add({ severity: 'success', summary: 'Role updated', life: 3000 });
  }

  async pauseStrategy(us: UserStrategy) {
    this.actionLoading = us.id;
    try {
      await this.adminService.pauseUserStrategyByAdmin(us.id);
      this.messageService.add({ severity: 'success', summary: 'Strategy paused', life: 3000 });
    } finally { this.actionLoading = null; }
  }

  async resumeStrategy(us: UserStrategy) {
    this.actionLoading = us.id;
    try {
      await this.adminService.resumeUserStrategyByAdmin(us.id);
      this.messageService.add({ severity: 'success', summary: 'Strategy resumed', life: 3000 });
    } finally { this.actionLoading = null; }
  }

  getStatusClass(status: string): string { return `status-${status}`; }

  formatDate(ts: any): string {
    if (!ts) return '—';
    const d = ts.toDate ? ts.toDate() : new Date(ts);
    return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
  }

  formatINR(value: number): string {
    return `₹${value.toLocaleString('en-IN')}`;
  }

  goBack() { this.router.navigate(['/admin/users']); }
}
