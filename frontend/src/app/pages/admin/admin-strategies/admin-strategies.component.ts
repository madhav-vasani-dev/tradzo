import { Component, OnInit, OnDestroy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ToastModule } from 'primeng/toast';
import { MessageService } from 'primeng/api';
import { Subscription } from 'rxjs';
import { StrategyService } from '../../../core/services/strategy.service';
import { Strategy } from '../../../models/strategy.model';
import { MOCK_STRATEGIES } from '../../strategies/strategies.mock';

@Component({
  selector: 'app-admin-strategies',
  standalone: true,
  imports: [CommonModule, FormsModule, ToastModule],
  templateUrl: './admin-strategies.component.html',
  styleUrl: './admin-strategies.component.scss',
  providers: [MessageService]
})
export class AdminStrategiesComponent implements OnInit {
  private messageService = inject(MessageService);

  strategies: Strategy[] = [];
  isLoading = true;
  searchQuery = '';
  togglingId: string | null = null;

  ngOnInit() {
    // Phase 1: use mock strategies — Phase 2 will load from Firestore.
    this.strategies = [...MOCK_STRATEGIES];
    this.isLoading = false;
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
    // Optimistic toggle
    strategy.isVisible = !strategy.isVisible;

    // In Phase 2 this will call StrategyService.updateStrategy()
    await new Promise(r => setTimeout(r, 600));

    this.messageService.add({
      severity: 'success',
      summary: strategy.isVisible ? 'Strategy visible' : 'Strategy hidden',
      detail: `${strategy.name} is now ${strategy.isVisible ? 'visible to' : 'hidden from'} users.`,
      life: 3000
    });
    this.togglingId = null;
  }

  formatINR(value: number): string {
    return `₹${value.toLocaleString('en-IN')}`;
  }
}
