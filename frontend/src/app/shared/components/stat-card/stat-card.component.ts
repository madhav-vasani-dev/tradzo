import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-stat-card',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="stat-card">
      <div class="stat-icon" [class]="iconClass">
        <i [class]="icon"></i>
      </div>
      <div class="stat-body">
        <div class="stat-label">{{ label }}</div>
        <div class="stat-value">{{ value }}</div>
        @if (trend !== null && trend !== undefined) {
          <div class="stat-trend" [class.positive]="trend >= 0" [class.negative]="trend < 0">
            <i [class]="trend >= 0 ? 'pi pi-arrow-up-right' : 'pi pi-arrow-down-right'"></i>
            {{ trend | number: '1.1-1' }}%
          </div>
        }
      </div>
    </div>
  `,
  styleUrl: './stat-card.component.scss'
})
export class StatCardComponent {
  @Input() label = '';
  @Input() value = '';
  @Input() icon = 'pi pi-chart-line';
  @Input() iconClass = 'icon-cyan';
  @Input() trend: number | null = null;
}
