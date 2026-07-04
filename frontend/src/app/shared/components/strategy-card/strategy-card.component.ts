import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { Strategy } from '../../../models/strategy.model';

@Component({
  selector: 'app-strategy-card',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './strategy-card.component.html',
  styleUrl: './strategy-card.component.scss'
})
export class StrategyCardComponent {
  @Input() strategy!: Strategy;
  @Input() isDeployed = false;
  @Input() animDelay = 1;
  @Output() deployClicked = new EventEmitter<Strategy>();

  getRiskClass(): string {
    return this.strategy.riskLevel.toLowerCase();
  }

  formatPercent(value: number): string {
    return `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`;
  }

  formatINR(value: number): string {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency', currency: 'INR', maximumFractionDigits: 0
    }).format(value);
  }
}
