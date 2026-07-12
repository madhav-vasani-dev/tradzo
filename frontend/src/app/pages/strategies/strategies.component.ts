import { Component, OnInit, OnDestroy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Auth, user } from '@angular/fire/auth';
import { ToastModule } from 'primeng/toast';
import { MessageService } from 'primeng/api';
import { DialogModule } from 'primeng/dialog';
import { Subscription } from 'rxjs';
import { StrategyCardComponent } from '../../shared/components/strategy-card/strategy-card.component';
import { DeployStrategyDialogComponent, DeployConfig } from '../../shared/components/deploy-strategy-dialog/deploy-strategy-dialog.component';
import { Strategy, StrategyCategory, RiskLevel, UserStrategy } from '../../models/strategy.model';
import { StrategyService } from '../../core/services/strategy.service';

type FilterCategory = StrategyCategory | 'All';
type FilterRisk = RiskLevel | 'All';

@Component({
  selector: 'app-strategies',
  standalone: true,
  imports: [CommonModule, FormsModule, StrategyCardComponent, DeployStrategyDialogComponent, ToastModule, DialogModule],
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
  userDeployments: UserStrategy[] = [];
  isLoading = true;
  showDeployDialog = false;
  deployTarget: Strategy | null = null;


  // Confirmation dialog properties
  showConfirm = false;
  confirmTitle = '';
  confirmMsg = '';
  confirmBtnText = 'Confirm';
  private actionToExecute: (() => Promise<void>) | null = null;

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
              this.userDeployments = userStrats;
              this.deployedIds = new Set(
                userStrats
                  .filter(us => us.status !== 'stopped')
                  .map(us => us.strategyId)
              );
            })
          );
        } else {
          this.userDeployments = [];
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
  
  getStrategyDeployment(strategyId: string): UserStrategy | undefined {
    return this.userDeployments.find(d => d.strategyId === strategyId && d.status !== 'stopped');
  }


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

  onToggleClicked(event: { strategy: Strategy; action: 'enable' | 'disable' }) {
    const strategy = event.strategy;
    const action = event.action;

    if (action === 'disable') {
      this.confirmTitle = 'Disable Strategy';
      this.confirmMsg = `Are you sure you want to disable ${strategy.name}? It will not execute orders for any future days until you enable it again.`;
      this.confirmBtnText = 'Disable';
      this.actionToExecute = async () => {
        const found = this.userDeployments.find(us => us.strategyId === strategy.id && us.status !== 'stopped');
        if (found) {
          await this.strategyService.pauseUserStrategy(found.id);
          this.messageService.add({
            severity: 'success',
            summary: 'Strategy Disabled',
            detail: `${strategy.name} has been disabled.`
          });
        }
      };
    } else {
      this.confirmTitle = 'Enable Strategy';
      this.confirmMsg = `Are you sure you want to enable ${strategy.name}? It will start executing orders automatically on future trading days.`;
      this.confirmBtnText = 'Enable';
      this.actionToExecute = async () => {
        const found = this.userDeployments.find(us => us.strategyId === strategy.id && us.status !== 'stopped');
        if (found) {
          await this.strategyService.resumeUserStrategy(found.id);
          this.messageService.add({
            severity: 'success',
            summary: 'Strategy Enabled',
            detail: `${strategy.name} is now enabled.`
          });
        }
      };
    }
    this.showConfirm = true;
  }


  async executeAction() {
    if (this.actionToExecute) {
      try {
        await this.actionToExecute();
      } catch (err) {
        console.error('Failed to execute action:', err);
      } finally {
        this.actionToExecute = null;
        this.showConfirm = false;
      }
    }
  }
}

