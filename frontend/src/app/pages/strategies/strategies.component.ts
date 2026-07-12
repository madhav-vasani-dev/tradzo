import { Component, OnInit, OnDestroy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Auth, user } from '@angular/fire/auth';
import { ToastModule } from 'primeng/toast';
import { MessageService } from 'primeng/api';
import { Subscription } from 'rxjs';
import { StrategyCardComponent } from '../../shared/components/strategy-card/strategy-card.component';
import { DeployStrategyDialogComponent, DeployConfig } from '../../shared/components/deploy-strategy-dialog/deploy-strategy-dialog.component';
import { Strategy, StrategyCategory, RiskLevel } from '../../models/strategy.model';
import { StrategyService } from '../../core/services/strategy.service';

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
export class StrategiesComponent implements OnInit, OnDestroy {
  private auth = inject(Auth);
  private messageService = inject(MessageService);
  private strategyService = inject(StrategyService);

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

  private subscriptions = new Subscription();

  ngOnInit() {
    // 1. Fetch available strategies from Firestore
    this.subscriptions.add(
      this.strategyService.getVisibleStrategies().subscribe({
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
            detail: 'Failed to load strategies.'
          });
        }
      })
    );

    // 2. Fetch user's deployments to track deployed strategies
    this.subscriptions.add(
      user(this.auth).subscribe((u) => {
        if (u) {
          this.subscriptions.add(
            this.strategyService.getUserStrategies(u.uid).subscribe((userStrats) => {
              // Only active/enabled/ready/trade_active count as currently deployed/active cards
              this.deployedIds = new Set(
                userStrats
                  .filter(us => us.status !== 'stopped')
                  .map(us => us.strategyId)
              );
            })
          );
        } else {
          this.deployedIds.clear();
        }
      })
    );
  }

  ngOnDestroy() {
    this.subscriptions.unsubscribe();
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

  async onDeployed(config: DeployConfig) {
    const currentUser = this.auth.currentUser;
    if (!currentUser) {
      this.messageService.add({
        severity: 'error',
        summary: 'Not Authenticated',
        detail: 'Please log in to deploy strategies.'
      });
      return;
    }

    try {
      this.isLoading = true;
      await this.strategyService.deployStrategy(
        currentUser.uid,
        config.strategy.id,
        config.strategyCode,
        config.strategy.name,
        config.brokerAccountId,
        config.brokerName,
        config.deployedAmount,
        config.multiplier
      );

      this.messageService.add({
        severity: 'success',
        summary: 'Strategy Deployed!',
        detail: `${config.strategy.name} deployed successfully. Code: ${config.strategyCode}, Multiplier: ${config.multiplier}x.`,
        life: 6000
      });
    } catch (err: any) {
      console.error('Error deploying strategy:', err);
      this.messageService.add({
        severity: 'error',
        summary: 'Deployment Failed',
        detail: err.message || 'An error occurred during deployment.'
      });
    } finally {
      this.isLoading = false;
    }
  }
}
