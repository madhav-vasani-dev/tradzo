import { Component, Input, Output, EventEmitter, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DialogModule } from 'primeng/dialog';
import { Auth } from '@angular/fire/auth';
import { Strategy } from '../../../models/strategy.model';

export interface DeployConfig {
  strategy: Strategy;
  brokerAccountId: string;
  brokerName: 'upstox' | 'jainam';
  brokerDisplayName: string;
  amount: number;
}

// Placeholder broker accounts — will come from Firestore once Broker module is built
const PLACEHOLDER_BROKERS = [
  { id: 'broker-placeholder-1', broker: 'upstox' as const, displayName: 'Upstox — Connect your account first', isConnected: false },
];

@Component({
  selector: 'app-deploy-strategy-dialog',
  standalone: true,
  imports: [CommonModule, FormsModule, DialogModule],
  templateUrl: './deploy-strategy-dialog.component.html',
  styleUrl: './deploy-strategy-dialog.component.scss'
})
export class DeployStrategyDialogComponent implements OnInit {
  @Input() strategy!: Strategy;
  @Input() visible = false;
  @Output() visibleChange = new EventEmitter<boolean>();
  @Output() deployed = new EventEmitter<DeployConfig>();

  private auth = inject(Auth);

  currentStep = 1;
  totalSteps = 3;
  isDeploying = false;

  brokers = PLACEHOLDER_BROKERS;
  selectedBroker: typeof PLACEHOLDER_BROKERS[0] | null = null;
  amount = 0;
  amountError = '';

  ngOnInit() {
    this.reset();
  }

  reset() {
    this.currentStep = 1;
    this.selectedBroker = null;
    this.amount = 0;
    this.amountError = '';
    this.isDeploying = false;
  }

  get canGoNext(): boolean {
    if (this.currentStep === 1) return !!this.selectedBroker && this.selectedBroker.isConnected;
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

    // Simulate deploy delay — will be replaced with real Firestore write
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

  selectBroker(broker: typeof PLACEHOLDER_BROKERS[0]) {
    this.selectedBroker = broker;
  }

  setQuickAmount(multiplier: number) {
    this.amount = this.strategy.minimumAmount * multiplier;
    this.validateAmount();
  }

  formatINR(value: number): string {
    return `₹${value.toLocaleString('en-IN')}`;
  }
}
