import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';

@Component({
  selector: 'app-broker-callback',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="callback-page">
      <div class="callback-card">
        @if (status === 'loading') {
          <div class="spinner"></div>
          <p class="status-text">Completing connection...</p>
        }
        @if (status === 'success') {
          <div class="icon-success"><i class="pi pi-check-circle"></i></div>
          <h2>Broker Connected!</h2>
          <p>Your {{ broker | titlecase }} account has been connected successfully.</p>
          <p class="redirect-note">Redirecting to Broker Accounts...</p>
        }
        @if (status === 'error') {
          <div class="icon-error"><i class="pi pi-times-circle"></i></div>
          <h2>Connection Failed</h2>
          <p>{{ errorMessage }}</p>
          <button class="retry-btn" (click)="goToBrokers()">Back to Broker Accounts</button>
        }
      </div>
    </div>
  `,
  styleUrl: './broker-callback.component.scss'
})
export class BrokerCallbackComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);

  status: 'loading' | 'success' | 'error' = 'loading';
  broker = '';
  errorMessage = '';

  ngOnInit() {
    const params = this.route.snapshot.queryParamMap;
    const success = params.get('status');
    const error = params.get('error');
    this.broker = params.get('broker') ?? 'broker';

    if (error) {
      this.status = 'error';
      this.errorMessage = this.parseError(error);
    } else if (success === 'success') {
      this.status = 'success';
      setTimeout(() => this.router.navigate(['/broker-accounts']), 2500);
    } else {
      // No recognized params — likely a direct navigation; just redirect
      this.router.navigate(['/broker-accounts']);
    }
  }

  private parseError(code: string): string {
    const map: Record<string, string> = {
      'access_denied': 'You denied access to your broker account.',
      'token_exchange_failed': 'Could not exchange the authorization code. Please try again.',
      'invalid_state': 'Security validation failed. Please try connecting again.',
    };
    return map[code] ?? 'An unexpected error occurred. Please try again.';
  }

  goToBrokers() {
    this.router.navigate(['/broker-accounts']);
  }
}
