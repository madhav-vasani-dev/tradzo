import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth.guard';
import { adminGuard } from './core/guards/admin.guard';

export const routes: Routes = [
  // Public
  { path: 'auth', loadComponent: () => import('./pages/auth/auth.component').then(m => m.AuthComponent) },

  // Broker OAuth callback — public, backend redirects here
  {
    path: 'broker/callback',
    loadComponent: () => import('./pages/broker-accounts/broker-callback/broker-callback.component').then(m => m.BrokerCallbackComponent)
  },

  // ── User routes ──────────────────────────────────────────────────────────
  {
    path: 'dashboard',
    loadComponent: () => import('./pages/dashboard/dashboard.component').then(m => m.DashboardComponent),
    canActivate: [authGuard]
  },
  {
    path: 'strategies',
    loadComponent: () => import('./pages/strategies/strategies.component').then(m => m.StrategiesComponent),
    canActivate: [authGuard]
  },
  {
    path: 'strategies/:id',
    loadComponent: () => import('./pages/strategies/strategy-detail/strategy-detail.component').then(m => m.StrategyDetailComponent),
    canActivate: [authGuard]
  },
  {
    path: 'broker-accounts',
    loadComponent: () => import('./pages/broker-accounts/broker-accounts.component').then(m => m.BrokerAccountsComponent),
    canActivate: [authGuard]
  },
  {
    path: 'pnl',
    loadComponent: () => import('./pages/pnl/pnl.component').then(m => m.PnlComponent),
    canActivate: [authGuard]
  },

  // ── Admin routes (authGuard + adminGuard) ────────────────────────────────
  {
    path: 'admin/users',
    loadComponent: () => import('./pages/admin/admin-users/admin-users.component').then(m => m.AdminUsersComponent),
    canActivate: [authGuard, adminGuard]
  },
  {
    path: 'admin/users/:uid',
    loadComponent: () => import('./pages/admin/admin-user-detail/admin-user-detail.component').then(m => m.AdminUserDetailComponent),
    canActivate: [authGuard, adminGuard]
  },
  {
    path: 'admin/strategies',
    loadComponent: () => import('./pages/admin/admin-strategies/admin-strategies.component').then(m => m.AdminStrategiesComponent),
    canActivate: [authGuard, adminGuard]
  },
  {
    path: 'admin/activity',
    loadComponent: () => import('./pages/admin/admin-activity/admin-activity.component').then(m => m.AdminActivityComponent),
    canActivate: [authGuard, adminGuard]
  },

  // Redirects — the dashboard is the app's landing page.
  { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
  { path: '**', redirectTo: 'dashboard' }
];
