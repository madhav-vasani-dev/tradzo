import { Component, inject, OnInit } from '@angular/core';
import { NavigationEnd, Router, RouterOutlet } from '@angular/router';
import { CommonModule } from '@angular/common';
import { ToastModule } from 'primeng/toast';
import { DrawerModule } from 'primeng/drawer';
import { ButtonModule } from 'primeng/button';
import { MenuModule } from 'primeng/menu';
import { MenuItem } from 'primeng/api';
import { Auth } from '@angular/fire/auth';
import { SidebarComponent } from './pages/sidebar/sidebar.component';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, ToastModule, CommonModule, DrawerModule, ButtonModule, MenuModule, SidebarComponent],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss'
})
export class AppComponent implements OnInit {
  private router = inject(Router);
  private auth = inject(Auth);

  sidebarVisible = false;
  desktopSidebarVisible = true;
  isAuthRoute = false;
  pageTitle = '';

  accountMenuItems: MenuItem[] = [];

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
          this.pageTitle = path.charAt(0).toUpperCase() + path.slice(1);
        }
      }
    });
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
