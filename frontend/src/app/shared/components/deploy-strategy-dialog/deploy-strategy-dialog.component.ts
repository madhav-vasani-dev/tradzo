import { Component, Input, Output, EventEmitter, OnInit, OnDestroy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DialogModule } from 'primeng/dialog';
import { Auth } from '@angular/fire/auth';
import { Subscription } from 'rxjs';
import { Strategy } from '../../../models/strategy.model';
import { BrokerAccount, BrokerName } from '../../../models/broker-account.model';
import { BrokerService } from '../../../core/services/broker.service';
import { formatMoney as fmtMoney } from '../../../core/format';

export interface DeployConfig {
  strategy: Strategy;
  brokerAccountId: string;
  brokerName: BrokerName;
  brokerDisplayName: string;
  multiplier: number;
  deployedAmount: number;
  strategyCode: string;
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
  multiplier = 1;

  readonly MULTIPLIER_OPTIONS = [1, 2, 3, 5, 10];

  private sub?: Subscription;

  ngOnInit() {
    this.reset();
    const user = this.auth.currentUser;
    if (user) {
      this.sub = this.brokerService.getUserBrokerAccounts(user.uid).subscribe((accounts: BrokerAccount[]) => {
        this.brokerAccounts = accounts.filter((a: BrokerAccount) => a.isConnected);
        if (this.strategy?.broker) {
          const matching = this.brokerAccounts.find((a: BrokerAccount) => a.broker === this.strategy.broker);
          if (matching) {
            this.selectedBroker = matching;
          }
        }
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
    this.multiplier = 1;
    this.isDeploying = false;
  }

  get hasConnectedBrokers(): boolean {
    return this.brokerAccounts.length > 0;
  }

  get deployedCapital(): number {
    return this.multiplier * (this.strategy?.minimumAmount || 0);
  }

  get canGoNext(): boolean {
    if (this.currentStep === 1) return !!this.selectedBroker;
    if (this.currentStep === 2) return this.multiplier >= 1;
    return true;
  }

  validateAmount() { /* no-op — multiplier is always valid */ }


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
      multiplier: this.multiplier,
      deployedAmount: this.deployedCapital,
      strategyCode: this.strategy.strategyCode,
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

  setMultiplier(value: number) {
    this.multiplier = value;
  }

  formatMoney(value: number): string {
    return fmtMoney(value, this.strategy?.currency);
  }
}
