import { Component, inject, OnInit, OnDestroy } from '@angular/core';
import { NavigationEnd, Router, RouterOutlet } from '@angular/router';
import { CommonModule } from '@angular/common';
import { ToastModule } from 'primeng/toast';
import { DrawerModule } from 'primeng/drawer';
import { ButtonModule } from 'primeng/button';
import { MenuModule } from 'primeng/menu';
import { MenuItem } from 'primeng/api';
import { Auth } from '@angular/fire/auth';
import { Subscription } from 'rxjs';
import { SidebarComponent } from './pages/sidebar/sidebar.component';
import { StrategyService } from './core/services/strategy.service';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, ToastModule, CommonModule, DrawerModule, ButtonModule, MenuModule, SidebarComponent],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss'
})
export class AppComponent implements OnInit, OnDestroy {
  private router = inject(Router);
  private auth = inject(Auth);
  private strategyService = inject(StrategyService);

  sidebarVisible = false;
  desktopSidebarVisible = true;
  isAuthRoute = false;
  pageTitle = '';
  isPaperTradingMode = false;

  accountMenuItems: MenuItem[] = [];
  private subscriptions = new Subscription();

  ngOnInit(): void {
    this.accountMenuItems = [
      { label: 'View Profile', icon: 'pi pi-user', command: () => this.router.navigate(['/profile']) },
      { label: 'Settings', icon: 'pi pi-cog', command: () => this.router.navigate(['/settings']) },
      { separator: true },
      { label: 'Logout', icon: 'pi pi-sign-out', command: () => this.logout() }
    ];

    this.router.events.subscribe((event) => {
      if (event instanceof NavigationEnd) {
        if (event.url === '/auth' || event.url.startsWith('/auth')) {
          this.isAuthRoute = true;
        } else {
          this.isAuthRoute = false;
        }

        const path = event.url.split('?')[0].split('/')[1];
        if (!path) {
          this.pageTitle = 'Dashboard';
        } else {
          // Convert kebab-case to Title Case (e.g., "broker-accounts" → "Broker Accounts")
          this.pageTitle = path
            .split('-')
            .map(word => word.charAt(0).toUpperCase() + word.slice(1))
            .join(' ');
        }
      }
    });

    // Subscribe to global trading mode (paper vs live)
    this.subscriptions.add(
      this.strategyService.getTradingMode().subscribe({
        next: (mode) => {
          this.isPaperTradingMode = !!mode?.paperTrading;
        },
        error: (err) => {
          console.error('Error fetching trading mode settings:', err);
        }
      })
    );
  }

  ngOnDestroy(): void {
    this.subscriptions.unsubscribe();
  }

  toggleSidebar() {
    if (typeof window !== 'undefined' && window.innerWidth >= 992) {
      this.desktopSidebarVisible = !this.desktopSidebarVisible;
    } else {
      this.sidebarVisible = !this.sidebarVisible;
    }
  }

  async logout() {
    await this.auth.signOut();
    localStorage.removeItem('sessionExpiry');
    this.router.navigate(['/auth']);
  }
}
