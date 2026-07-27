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
import { ConnectBrokerDialogComponent } from '../../shared/components/connect-broker-dialog/connect-broker-dialog.component';
import { formatDate } from '../../core/format';

@Component({
  selector: 'app-broker-accounts',
  standalone: true,
  imports: [CommonModule, ToastModule, ConnectBrokerDialogComponent],
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

  // Connect-broker dialog state
  dialogVisible = false;
  dialogMeta: BrokerMeta | null = null;

  private sub?: Subscription;

  ngOnInit() {
    this.loadAccounts();
  }

  private loadAccounts() {
    const user = this.auth.currentUser;
    if (!user) { this.isLoading = false; return; }

    this.sub?.unsubscribe();
    console.log('LOAD ACCOUNTS')
    this.sub = this.brokerService.getUserBrokerAccounts(user.uid).subscribe({
      next: (accounts) => {
        console.log('ACCOUTNS LOADED', accounts)
        this.connectedAccounts = accounts;
        this.isLoading = false;
      },
      error: (err) => {
        // Almost always a Firestore rules "permission-denied" — log the real code.
        console.error('[BrokerAccounts] Failed to load broker accounts:', err?.code, err?.message, err);
        this.messageService.add({
          severity: 'error',
          summary: 'Could not load accounts',
          detail: err?.code === 'permission-denied'
            ? 'Firestore rules are blocking access to your broker accounts.'
            : (err?.message || 'Failed to load broker accounts.'),
          life: 6000
        });
        this.isLoading = false;
      }
    });
  }

  ngOnDestroy() { this.sub?.unsubscribe(); }

  /** The account doc for a broker, whether connected or disconnected. */
  getAccount(broker: string): BrokerAccount | undefined {
    return this.connectedAccounts.find(a => a.broker === broker);
  }

  isConnected(broker: string): boolean {
    return !!this.getAccount(broker)?.isConnected;
  }

  /** True when an account exists (so its API keys are saved for reconnect). */
  hasSavedAccount(broker: string): boolean {
    return !!this.getAccount(broker);
  }

  /** Open the credential dialog for a broker (bring-your-own-key). */
  connectBroker(meta: BrokerMeta) {
    if (meta.comingSoon) return;
    if (!this.auth.currentUser) {
      this.messageService.add({ severity: 'warn', summary: 'Not logged in', detail: 'Please log in first.' });
      return;
    }
    this.dialogMeta = meta;
    this.dialogVisible = true;
  }

  reconnectingId: string | null = null;

  /** Reconnect an existing account using its stored keys (no re-entering). */
  async reconnectBroker(account: BrokerAccount) {
    this.reconnectingId = account.id;
    try {
      const res = await this.brokerService.reconnectBroker(account.id);
      if (res.auth_url) {
        // Upstox: hand off to the broker login page.
        window.location.href = res.auth_url;
        return;
      }
      // Jainam: reconnected synchronously.
      this.messageService.add({
        severity: 'success',
        summary: 'Reconnected',
        detail: `${account.displayName} reconnected successfully.`,
        life: 4000
      });
      this.loadAccounts();
    } catch (err: any) {
      this.messageService.add({
        severity: 'error',
        summary: 'Reconnect Failed',
        detail: err?.message || 'Could not reconnect. Please try again.',
        life: 6000
      });
    } finally {
      this.reconnectingId = null;
    }
  }

  /** Fired when a synchronous (session) broker connects successfully. */
  onBrokerConnected() {
    this.messageService.add({
      severity: 'success',
      summary: 'Broker Connected',
      detail: `${this.dialogMeta?.label} account connected successfully.`,
      life: 4000
    });
    this.loadAccounts();
  }

  async disconnectBroker(account: BrokerAccount) {
    try {
      await this.brokerService.disconnectBroker(account.id);
      this.messageService.add({
        severity: 'success',
        summary: 'Disconnected',
        detail: `${account.broker} disconnected. Your API keys are saved — reconnect anytime.`,
        life: 5000
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

  removingId: string | null = null;

  /** Fully forget an account, including its stored API keys. */
  async removeBroker(account: BrokerAccount) {
    this.removingId = account.id;
    try {
      await this.brokerService.removeBroker(account.id);
      this.messageService.add({
        severity: 'info',
        summary: 'Account removed',
        detail: `${account.displayName} removed. You'll need to re-enter your API keys to connect again.`,
        life: 5000
      });
    } catch (err: any) {
      this.messageService.add({
        severity: 'error',
        summary: 'Error',
        detail: err?.message || 'Could not remove the account.',
        life: 4000
      });
    } finally {
      this.removingId = null;
    }
  }

  formatDate(ts: any): string {
    if (!ts) return '—';
    const date = ts.toDate ? ts.toDate() : new Date(ts);
    return formatDate(date, { day: 'numeric', month: 'short', year: 'numeric' });
  }

  formatExpiry(ts: any): string {
    if (!ts) return 'Unknown';
    const date = ts.toDate ? ts.toDate() : new Date(ts);
    const now = new Date();
    const diffH = Math.round((date.getTime() - now.getTime()) / 3600000);
    if (diffH < 0) return 'Expired';
    if (diffH < 1) return 'Expiring soon';
    if (diffH < 24) return `Expires in ${diffH}h`;
    return `Expires ${formatDate(date, { day: 'numeric', month: 'short' })}`;
  }
}
