import { Component, OnInit, OnDestroy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ToastModule } from 'primeng/toast';
import { MessageService } from 'primeng/api';
import { Subscription } from 'rxjs';
import { StrategyService } from '../../../core/services/strategy.service';
import { Strategy } from '../../../models/strategy.model';
import { MOCK_STRATEGIES } from '../../strategies/strategies.mock';
import { formatMoney, CurrencyCode } from '../../../core/format';

@Component({
  selector: 'app-admin-strategies',
  standalone: true,
  imports: [CommonModule, FormsModule, ToastModule],
  templateUrl: './admin-strategies.component.html',
  styleUrl: './admin-strategies.component.scss',
  providers: [MessageService]
})
export class AdminStrategiesComponent implements OnInit, OnDestroy {
  private messageService = inject(MessageService);
  private strategyService = inject(StrategyService);

  strategies: Strategy[] = [];
  isLoading = true;
  searchQuery = '';
  togglingId: string | null = null;

  private sub = new Subscription();

  ngOnInit() {
    this.isLoading = true;
    this.sub.add(
      this.strategyService.getAllStrategies().subscribe({
        next: (data) => {
          this.strategies = data;
          this.isLoading = false;
        },
        error: (err) => {
          console.error('Error fetching strategies:', err);
          this.isLoading = false;
          this.messageService.add({
            severity: 'error',
            summary: 'Error',
            detail: 'Failed to fetch strategies from database.'
          });
        }
      })
    );
  }

  ngOnDestroy() {
    this.sub.unsubscribe();
  }

  get filteredStrategies(): Strategy[] {
    if (!this.searchQuery) return this.strategies;
    const q = this.searchQuery.toLowerCase();
    return this.strategies.filter(s =>
      s.name.toLowerCase().includes(q) ||
      s.category.toLowerCase().includes(q)
    );
  }

  get activeCount(): number { return this.strategies.filter(s => s.isVisible).length; }

  async toggleVisibility(strategy: Strategy) {
    this.togglingId = strategy.id;
    const newVisibility = !strategy.isVisible;

    try {
      await this.strategyService.toggleVisibility(strategy.id, newVisibility);
      this.messageService.add({
        severity: 'success',
        summary: newVisibility ? 'Strategy visible' : 'Strategy hidden',
        detail: `${strategy.name} is now ${newVisibility ? 'visible to' : 'hidden from'} users.`,
        life: 3000
      });
    } catch (err: any) {
      console.error('Error toggling strategy visibility:', err);
      this.messageService.add({
        severity: 'error',
        summary: 'Toggle Failed',
        detail: 'Failed to update visibility in Firestore.'
      });
    } finally {
      this.togglingId = null;
    }
  }

  formatMoney(value: number | null | undefined, currency?: CurrencyCode): string {
    return formatMoney(value, currency);
  }
}

