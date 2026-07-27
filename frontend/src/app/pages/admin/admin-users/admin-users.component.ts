import { Component, OnInit, OnDestroy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { ToastModule } from 'primeng/toast';
import { MessageService } from 'primeng/api';
import { Subscription } from 'rxjs';
import { AdminService } from '../../../core/services/admin.service';
import { AuthService } from '../../../core/services/auth.service';
import { TradzoUser } from '../../../models/user.model';
import { formatDate as formatDateUtil } from '../../../core/format';

@Component({
  selector: 'app-admin-users',
  standalone: true,
  imports: [CommonModule, FormsModule, ToastModule],
  templateUrl: './admin-users.component.html',
  styleUrl: './admin-users.component.scss',
  providers: [MessageService]
})
export class AdminUsersComponent implements OnInit, OnDestroy {
  private adminService = inject(AdminService);
  private authService = inject(AuthService);
  private messageService = inject(MessageService);
  private router = inject(Router);

  users: TradzoUser[] = [];
  isLoading = true;
  searchQuery = '';
  filterRole: 'all' | 'admin' | 'user' = 'all';
  togglingUid: string | null = null;

  private sub?: Subscription;

  ngOnInit() {
    this.sub = this.adminService.getAllUsers().subscribe({
      next: (users) => { this.users = users; this.isLoading = false; },
      error: () => { this.isLoading = false; }
    });
  }

  ngOnDestroy() { this.sub?.unsubscribe(); }

  get filteredUsers(): TradzoUser[] {
    return this.users.filter(u => {
      const matchSearch = !this.searchQuery ||
        u.username?.toLowerCase().includes(this.searchQuery.toLowerCase()) ||
        u.email?.toLowerCase().includes(this.searchQuery.toLowerCase());
      const matchRole = this.filterRole === 'all' ||
        (this.filterRole === 'admin' && (u.isAdmin || u.isSuperUser)) ||
        (this.filterRole === 'user' && !u.isAdmin && !u.isSuperUser);
      return matchSearch && matchRole;
    });
  }

  get totalAdmins(): number { return this.users.filter(u => u.isAdmin || u.isSuperUser).length; }
  get totalUsers(): number { return this.users.length; }

  async toggleAdmin(user: TradzoUser) {
    if (user.isSuperUser) {
      this.messageService.add({ severity: 'warn', summary: 'Cannot modify superuser', detail: 'Superuser role cannot be changed from the UI.' });
      return;
    }
    this.togglingUid = user.uid;
    try {
      await this.adminService.setAdminRole(user.uid, !user.isAdmin);
      this.messageService.add({
        severity: 'success',
        summary: user.isAdmin ? 'Admin role removed' : 'Admin role granted',
        detail: `${user.username || user.email} role updated.`,
        life: 4000
      });
    } catch {
      this.messageService.add({ severity: 'error', summary: 'Error', detail: 'Could not update role.' });
    } finally {
      this.togglingUid = null;
    }
  }

  viewUser(uid: string) { this.router.navigate(['/admin/users', uid]); }

  getRoleBadge(user: TradzoUser): string {
    if (user.isSuperUser) return 'Super Admin';
    if (user.isAdmin) return 'Admin';
    return 'User';
  }

  getRoleClass(user: TradzoUser): string {
    if (user.isSuperUser) return 'role-super';
    if (user.isAdmin) return 'role-admin';
    return 'role-user';
  }

  formatDate(ts: any): string {
    if (!ts) return '—';
    const d = ts.toDate ? ts.toDate() : ts;
    return formatDateUtil(d, { day: 'numeric', month: 'short', year: 'numeric' });
  }
}
