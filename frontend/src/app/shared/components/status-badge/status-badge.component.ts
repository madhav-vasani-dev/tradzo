import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

export type BadgeStatus = 'active' | 'paused' | 'stopped' | 'pending';
export type BadgeRisk = 'Low' | 'Medium' | 'High';

@Component({
  selector: 'app-status-badge',
  standalone: true,
  imports: [CommonModule],
  template: `
    <span class="badge" [class]="badgeClass">
      <span class="dot"></span>
      {{ label }}
    </span>
  `,
  styleUrl: './status-badge.component.scss'
})
export class StatusBadgeComponent {
  @Input() status: BadgeStatus = 'pending';

  get badgeClass(): string {
    return `badge-${this.status}`;
  }

  get label(): string {
    return this.status.charAt(0).toUpperCase() + this.status.slice(1);
  }
}
