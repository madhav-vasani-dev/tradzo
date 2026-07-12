import { Injectable, Injector, inject, runInInjectionContext } from '@angular/core';
import {
  Firestore,
  collection,
  collectionData,
  query,
  where
} from '@angular/fire/firestore';
import { Observable } from 'rxjs';
import { BrokerAccount, BrokerName } from '../../models/broker-account.model';
import { BACKEND_BASE_URL } from '../config';

const API_BASE = BACKEND_BASE_URL;

@Injectable({ providedIn: 'root' })
export class BrokerService {
  private firestore = inject(Firestore);
  private injector = inject(Injector);

  // ── Firestore reads ───────────────────────────────────────────────────────

  /**
   * Get all connected broker accounts for the current user.
   *
   * Wrapped in runInInjectionContext because this is called from a component's
   * ngOnInit (not an injection context). Without it, AngularFire can't bind the
   * stream to Angular's zone, so emissions land outside change detection and the
   * UI appears to hang until the next tick.
   */
  getUserBrokerAccounts(userId: string): Observable<BrokerAccount[]> {
    return runInInjectionContext(this.injector, () => {
      const ref = query(
        collection(this.firestore, 'brokerAccounts'),
        where('userId', '==', userId)
      );
      return collectionData(ref, { idField: 'id' }) as Observable<BrokerAccount[]>;
    });
  }

  /** Get a single broker account by broker name for a user */
  getBrokerAccount(userId: string, broker: BrokerName): Observable<BrokerAccount | null> {
    return runInInjectionContext(this.injector, () => {
      const ref = query(
        collection(this.firestore, 'brokerAccounts'),
        where('userId', '==', userId),
        where('broker', '==', broker)
      );
      return collectionData(ref, { idField: 'id' }) as Observable<BrokerAccount[]> as any;
    });
  }

  // ── Connect flow (bring-your-own-key, delegates to Python backend) ────────

  /**
   * Connect a broker using the user's OWN API credentials.
   *
   * Posts `{ userId, ...creds }` to `/broker/{broker}/connect`. The backend:
   *  - Upstox (oauth): returns `{ auth_url }` — caller redirects the browser there.
   *  - Jainam (session): logs in synchronously and returns `{ status: 'connected' }`.
   *
   * Returns the raw response so the caller can branch on `auth_url`.
   */
  async connectBroker(
    broker: BrokerName,
    userId: string,
    creds: Record<string, string>
  ): Promise<{ auth_url?: string; status?: string }> {
    const response = await fetch(`${API_BASE}/broker/${broker}/connect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ userId, ...creds }),
    });
    if (!response.ok) {
      let detail = 'Failed to connect broker. Make sure the backend is running.';
      try {
        const err = await response.json();
        if (err?.detail) detail = typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail);
      } catch { /* keep default */ }
      throw new Error(detail);
    }
    return response.json();
  }

  /**
   * Reconnect an existing account using the API credentials already stored in
   * the backend — the user does NOT re-enter their keys.
   *  - Upstox → returns `{ auth_url }`; caller redirects to Upstox to log in.
   *  - Jainam → re-logs in synchronously and returns `{ status: 'connected' }`.
   */
  async reconnectBroker(accountId: string): Promise<{ auth_url?: string; status?: string }> {
    const response = await fetch(`${API_BASE}/broker/reconnect/${accountId}`, {
      method: 'POST',
    });
    if (!response.ok) {
      let detail = 'Could not reconnect. Make sure the backend is running.';
      try {
        const err = await response.json();
        if (err?.detail) detail = typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail);
      } catch { /* keep default */ }
      throw new Error(detail);
    }
    return response.json();
  }

  /**
   * Disconnect: backend revokes the active session token and marks the account
   * disconnected, but KEEPS the stored API keys so the user can reconnect
   * without re-entering them. The Firestore listener updates the UI in realtime.
   */
  async disconnectBroker(brokerAccountId: string): Promise<void> {
    const resp = await fetch(`${API_BASE}/broker/disconnect/${brokerAccountId}`, { method: 'POST' });
    if (!resp.ok) throw new Error('Failed to disconnect the account.');
  }

  /**
   * Remove: fully forget the account — deletes the token, the stored API
   * credentials, and the Firestore document. The user must re-enter keys to
   * connect again.
   */
  async removeBroker(brokerAccountId: string): Promise<void> {
    const resp = await fetch(`${API_BASE}/broker/remove/${brokerAccountId}`, { method: 'POST' });
    if (!resp.ok) throw new Error('Failed to remove the account.');
  }
}
