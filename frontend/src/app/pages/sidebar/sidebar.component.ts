import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';

@Component({
  selector: 'app-sidebar',
  imports: [CommonModule, RouterModule],
  templateUrl: './sidebar.component.html',
  styleUrl: './sidebar.component.scss'
})
export class SidebarComponent {

  menuItems = [
    { label: 'Dashboard', icon: 'pi pi-objects-column', route: '/dashboard' },
    { label: 'Seasonality', icon: 'pi pi-calendar', route: '/seasonality' },
  ];
}
