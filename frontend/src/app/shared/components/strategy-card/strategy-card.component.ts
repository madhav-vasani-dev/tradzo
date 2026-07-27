import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { Strategy, UserStrategy } from '../../../models/strategy.model';
import { formatMoney as fmtMoney } from '../../../core/format';

@Component({
  selector: 'app-strategy-card',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './strategy-card.component.html',
  styleUrl: './strategy-card.component.scss'
})
export class StrategyCardComponent {
  @Input() strategy!: Strategy;
  @Input() deployment: UserStrategy | undefined;
  @Input() animDelay = 1;
  @Output() deployClicked = new EventEmitter<Strategy>();
  @Output() toggleClicked = new EventEmitter<{ strategy: Strategy; action: 'enable' | 'disable' }>();

  getRiskClass(): string {
    return this.strategy.riskLevel.toLowerCase();
  }

  formatPercent(value: number): string {
    return `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`;
  }


  formatMoney(value: number): string {
    return fmtMoney(value, this.strategy?.currency);
  }

}
