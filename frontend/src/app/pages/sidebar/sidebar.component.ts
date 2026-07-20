import { Component, inject } from '@angular/core';
import { CommonModule, AsyncPipe } from '@angular/common';
import { RouterModule } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';

interface MenuItem {
  label: string;
  icon: string;
  route: string;
  adminOnly?: boolean;
}

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [CommonModule, RouterModule, AsyncPipe],
  templateUrl: './sidebar.component.html',
  styleUrl: './sidebar.component.scss'
})
export class SidebarComponent {
  authService = inject(AuthService);

  mainMenuItems: MenuItem[] = [
    { label: 'Dashboard',       icon: 'pi pi-objects-column', route: '/dashboard' },
    { label: 'Strategies',      icon: 'pi pi-chart-bar',      route: '/strategies' },
    { label: 'Broker Accounts', icon: 'pi pi-building',       route: '/broker-accounts' },
    { label: 'P&L Report',      icon: 'pi pi-percentage',     route: '/pnl' },
    { label: 'Profile',         icon: 'pi pi-user',           route: '/profile' },
  ];

  adminMenuItems: MenuItem[] = [
    { label: 'Users',               icon: 'pi pi-users',          route: '/admin/users',       adminOnly: true },
    { label: 'Strategy Management', icon: 'pi pi-sliders-h',      route: '/admin/strategies',  adminOnly: true },
    { label: 'Activity Monitor',    icon: 'pi pi-desktop',        route: '/admin/activity',    adminOnly: true },
  ];
}
