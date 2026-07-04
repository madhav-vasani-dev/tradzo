import { Component, OnInit, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Auth } from '@angular/fire/auth';
import { StrategyService } from '../../core/services/strategy.service';
import { StrategyCardComponent } from '../../shared/components/strategy-card/strategy-card.component';
import { Strategy, StrategyCategory, RiskLevel } from '../../models/strategy.model';
import { MOCK_STRATEGIES } from './strategies.mock';

type FilterCategory = StrategyCategory | 'All';
type FilterRisk = RiskLevel | 'All';

@Component({
  selector: 'app-strategies',
  standalone: true,
  imports: [CommonModule, FormsModule, StrategyCardComponent],
  templateUrl: './strategies.component.html',
  styleUrl: './strategies.component.scss'
})
export class StrategiesComponent implements OnInit {
  private auth = inject(Auth);

  searchQuery = '';
  selectedCategory: FilterCategory = 'All';
  selectedRisk: FilterRisk = 'All';

  strategies: Strategy[] = [];
  deployedIds: Set<string> = new Set();
  isLoading = true;

  categories: FilterCategory[] = ['All', 'Options', 'Futures', 'Equity', 'Index'];
  riskLevels: FilterRisk[] = ['All', 'Low', 'Medium', 'High'];

  ngOnInit() {
    // Use mock data for Phase 1 — replace with Firestore query in production
    setTimeout(() => {
      this.strategies = MOCK_STRATEGIES;
      this.isLoading = false;
    }, 600);
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
    // Will open DeployStrategyDialog in next step
    console.log('Deploy:', strategy.name);
  }
}
