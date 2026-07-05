import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth.guard';

export const routes: Routes = [
  // Public
  { path: 'auth', loadComponent: () => import('./pages/auth/auth.component').then(m => m.AuthComponent) },

  // Auth-guarded user routes
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

  // Redirects
  { path: '', redirectTo: 'strategies', pathMatch: 'full' },
  { path: '**', redirectTo: 'strategies' }
];
