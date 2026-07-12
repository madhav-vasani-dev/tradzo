import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Auth } from '@angular/fire/auth';
import { ToastModule } from 'primeng/toast';
import { MessageService } from 'primeng/api';
import { StrategyCardComponent } from '../../shared/components/strategy-card/strategy-card.component';
import { DeployStrategyDialogComponent, DeployConfig } from '../../shared/components/deploy-strategy-dialog/deploy-strategy-dialog.component';
import { Strategy, StrategyCategory, RiskLevel } from '../../models/strategy.model';
import { MOCK_STRATEGIES } from './strategies.mock';

type FilterCategory = StrategyCategory | 'All';
type FilterRisk = RiskLevel | 'All';

@Component({
  selector: 'app-strategies',
  standalone: true,
  imports: [CommonModule, FormsModule, StrategyCardComponent, DeployStrategyDialogComponent, ToastModule],
  templateUrl: './strategies.component.html',
  styleUrl: './strategies.component.scss',
  providers: [MessageService]
})
export class StrategiesComponent implements OnInit {
  private auth = inject(Auth);
  private messageService = inject(MessageService);

  searchQuery = '';
  selectedCategory: FilterCategory = 'All';
  selectedRisk: FilterRisk = 'All';

  strategies: Strategy[] = [];
  deployedIds: Set<string> = new Set();
  isLoading = true;
  showDeployDialog = false;
  deployTarget: Strategy | null = null;

  categories: FilterCategory[] = ['All', 'Options', 'Futures', 'Equity', 'Index'];
  riskLevels: FilterRisk[] = ['All', 'Low', 'Medium', 'High'];

  ngOnInit() {
    // Use mock data for Phase 1 — replace with Firestore query in production.
    this.strategies = MOCK_STRATEGIES;
    this.isLoading = false;
  }

  get filteredStrategies(): Strategy[] {
    return this.strategies.filter(s => {
      const matchesSearch = !this.searchQuery ||
        s.name.toLowerCase().includes(this.searchQuery.toLowerCase()) ||
        s.tags.some(t => t.toLowerCase().includes(this.searchQuery.toLowerCase()));
      const matchesCategory = this.selectedCategory === 'All' || s.category === this.selectedCategory;
      const matchesRisk = this.selectedRisk === 'All' || s.riskLevel === this.selectedRisk;
      return matchesSearch && matchesCategory && matchesRisk;
    });
  }

  setCategory(cat: FilterCategory) { this.selectedCategory = cat; }
  setRisk(risk: FilterRisk) { this.selectedRisk = risk; }
  isDeployed(id: string): boolean { return this.deployedIds.has(id); }

  onDeployClicked(strategy: Strategy) {
    this.deployTarget = strategy;
    this.showDeployDialog = true;
  }

  onDeployed(config: DeployConfig) {
    this.deployedIds.add(config.strategy.id);
    this.messageService.add({
      severity: 'success',
      summary: 'Strategy Deployed!',
      detail: `${config.strategy.name} will go live at 9:15 AM IST on the next market day.`,
      life: 6000
    });
  }
}
