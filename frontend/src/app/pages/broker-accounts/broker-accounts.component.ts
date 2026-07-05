import { Component, OnInit, inject, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { ToastModule } from 'primeng/toast';
import { MessageService } from 'primeng/api';
import { Auth } from '@angular/fire/auth';
import { Subscription } from 'rxjs';
import { BrokerService } from '../../core/services/broker.service';
import { AuthService } from '../../core/services/auth.service';
import { BrokerAccount, BrokerMeta, BROKER_REGISTRY } from '../../models/broker-account.model';

@Component({
  selector: 'app-broker-accounts',
  standalone: true,
  imports: [CommonModule, ToastModule],
  templateUrl: './broker-accounts.component.html',
  styleUrl: './broker-accounts.component.scss',
  providers: [MessageService]
})
export class BrokerAccountsComponent implements OnInit, OnDestroy {
  private auth = inject(Auth);
  private authService = inject(AuthService);
  private brokerService = inject(BrokerService);
  private messageService = inject(MessageService);
  private router = inject(Router);

  brokerRegistry = BROKER_REGISTRY;
  connectedAccounts: BrokerAccount[] = [];
  isLoading = true;
  connectingBroker: string | null = null;

  private sub?: Subscription;

  ngOnInit() {
    const user = this.auth.currentUser;
    if (!user) { this.isLoading = false; return; }

    this.sub = this.brokerService.getUserBrokerAccounts(user.uid).subscribe({
      next: (accounts) => {
        this.connectedAccounts = accounts;
        this.isLoading = false;
      },
      error: () => { this.isLoading = false; }
    });
  }

  ngOnDestroy() { this.sub?.unsubscribe(); }

  /** Check if a broker is already connected */
  getAccount(broker: string): BrokerAccount | undefined {
    return this.connectedAccounts.find(a => a.broker === broker && a.isConnected);
  }

  isConnected(broker: string): boolean {
    return !!this.getAccount(broker);
  }

  async connectBroker(meta: BrokerMeta) {
    if (meta.comingSoon) return;
    const user = this.auth.currentUser;
    if (!user) {
      this.messageService.add({ severity: 'warn', summary: 'Not logged in', detail: 'Please log in first.' });
      return;
    }

    this.connectingBroker = meta.name;

    try {
      const authUrl = await this.brokerService.getUpstoxAuthUrl(user.uid);
      // Redirect user to Upstox OAuth page
      window.location.href = authUrl;
    } catch (err) {
      this.connectingBroker = null;
      this.messageService.add({
        severity: 'error',
        summary: 'Connection Failed',
        detail: 'Could not reach the trading server. Make sure the backend is running.',
        life: 6000
      });
    }
  }

  async disconnectBroker(account: BrokerAccount) {
    try {
      await this.brokerService.disconnectBroker(account.id);
      this.messageService.add({
        severity: 'success',
        summary: 'Disconnected',
        detail: `${account.broker} account disconnected successfully.`,
        life: 4000
      });
    } catch {
      this.messageService.add({
        severity: 'error',
        summary: 'Error',
        detail: 'Could not disconnect the account. Please try again.',
        life: 4000
      });
    }
  }

  formatDate(ts: any): string {
    if (!ts) return '—';
    const date = ts.toDate ? ts.toDate() : new Date(ts);
    return date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
  }

  formatExpiry(ts: any): string {
    if (!ts) return 'Unknown';
    const date = ts.toDate ? ts.toDate() : new Date(ts);
    const now = new Date();
    const diffH = Math.round((date.getTime() - now.getTime()) / 3600000);
    if (diffH < 0) return 'Expired';
    if (diffH < 1) return 'Expiring soon';
    if (diffH < 24) return `Expires in ${diffH}h`;
    return `Expires ${date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}`;
  }
}
