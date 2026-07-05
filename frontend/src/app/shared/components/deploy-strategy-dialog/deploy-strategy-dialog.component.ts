import { Component, Input, Output, EventEmitter, OnInit, OnDestroy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DialogModule } from 'primeng/dialog';
import { Auth } from '@angular/fire/auth';
import { Subscription } from 'rxjs';
import { Strategy } from '../../../models/strategy.model';
import { BrokerAccount } from '../../../models/broker-account.model';
import { BrokerService } from '../../../core/services/broker.service';

export interface DeployConfig {
  strategy: Strategy;
  brokerAccountId: string;
  brokerName: 'upstox' | 'jainam';
  brokerDisplayName: string;
  amount: number;
}

@Component({
  selector: 'app-deploy-strategy-dialog',
  standalone: true,
  imports: [CommonModule, FormsModule, DialogModule],
  templateUrl: './deploy-strategy-dialog.component.html',
  styleUrl: './deploy-strategy-dialog.component.scss'
})
export class DeployStrategyDialogComponent implements OnInit, OnDestroy {
  @Input() strategy!: Strategy;
  @Input() visible = false;
  @Output() visibleChange = new EventEmitter<boolean>();
  @Output() deployed = new EventEmitter<DeployConfig>();

  private auth = inject(Auth);
  private brokerService = inject(BrokerService);

  currentStep = 1;
  totalSteps = 3;
  isDeploying = false;

  brokerAccounts: BrokerAccount[] = [];
  loadingBrokers = true;
  selectedBroker: BrokerAccount | null = null;
  amount = 0;
  amountError = '';

  private sub?: Subscription;

  ngOnInit() {
    this.reset();
    const user = this.auth.currentUser;
    if (user) {
      this.sub = this.brokerService.getUserBrokerAccounts(user.uid).subscribe((accounts: BrokerAccount[]) => {
        this.brokerAccounts = accounts.filter((a: BrokerAccount) => a.isConnected);

        this.loadingBrokers = false;
      });
    } else {
      this.loadingBrokers = false;
    }
  }

  ngOnDestroy() { this.sub?.unsubscribe(); }

  reset() {
    this.currentStep = 1;
    this.selectedBroker = null;
    this.amount = 0;
    this.amountError = '';
    this.isDeploying = false;
  }

  get hasConnectedBrokers(): boolean {
    return this.brokerAccounts.length > 0;
  }

  get canGoNext(): boolean {
    if (this.currentStep === 1) return !!this.selectedBroker;
    if (this.currentStep === 2) return this.amount >= this.strategy.minimumAmount;
    return true;
  }

  get amountProgress(): number {
    if (!this.strategy || this.amount <= 0) return 0;
    return Math.min((this.amount / this.strategy.minimumAmount) * 100, 100);
  }

  validateAmount() {
    if (this.amount <= 0) {
      this.amountError = 'Please enter an amount';
    } else if (this.amount < this.strategy.minimumAmount) {
      this.amountError = `Minimum amount is ₹${this.strategy.minimumAmount.toLocaleString('en-IN')}`;
    } else {
      this.amountError = '';
    }
  }

  next() {
    if (!this.canGoNext) return;
    if (this.currentStep < this.totalSteps) this.currentStep++;
  }

  prev() {
    if (this.currentStep > 1) this.currentStep--;
  }

  async confirm() {
    if (!this.selectedBroker || !this.strategy) return;
    this.isDeploying = true;
    await new Promise(r => setTimeout(r, 1200));

    this.deployed.emit({
      strategy: this.strategy,
      brokerAccountId: this.selectedBroker.id,
      brokerName: this.selectedBroker.broker,
      brokerDisplayName: this.selectedBroker.displayName,
      amount: this.amount
    });

    this.isDeploying = false;
    this.close();
  }

  close() {
    this.reset();
    this.visibleChange.emit(false);
  }

  selectBroker(account: BrokerAccount) {
    this.selectedBroker = account;
  }

  setQuickAmount(multiplier: number) {
    this.amount = this.strategy.minimumAmount * multiplier;
    this.validateAmount();
  }

  formatINR(value: number): string {
    return `₹${value.toLocaleString('en-IN')}`;
  }
}
