import { Injectable, inject } from '@angular/core';
import {
  Firestore,
  collection,
  collectionData,
  doc,
  docData,
  query,
  where,
  updateDoc,
  deleteDoc,
  serverTimestamp
} from '@angular/fire/firestore';
import { Observable, of } from 'rxjs';
import { BrokerAccount, BrokerName } from '../../models/broker-account.model';

// Backend API base URL — will be set in environment once FastAPI is running
const API_BASE = 'http://localhost:8000';

@Injectable({ providedIn: 'root' })
export class BrokerService {
  private firestore = inject(Firestore);

  // ── Firestore reads ───────────────────────────────────────────────────────

  /** Get all connected broker accounts for the current user */
  getUserBrokerAccounts(userId: string): Observable<BrokerAccount[]> {
    const ref = query(
      collection(this.firestore, 'brokerAccounts'),
      where('userId', '==', userId)
    );
    return collectionData(ref, { idField: 'id' }) as Observable<BrokerAccount[]>;
  }

  /** Get a single broker account by broker name for a user */
  getBrokerAccount(userId: string, broker: BrokerName): Observable<BrokerAccount | null> {
    const ref = query(
      collection(this.firestore, 'brokerAccounts'),
      where('userId', '==', userId),
      where('broker', '==', broker)
    );
    return collectionData(ref, { idField: 'id' }) as Observable<BrokerAccount[]> as any;
  }

  // ── OAuth flow (delegates to Python backend) ──────────────────────────────

  /**
   * Step 1: Get Upstox authorization URL from backend.
   * Backend constructs: https://api.upstox.com/v2/login/authorization/dialog?...
   * and returns the full URL for us to redirect to.
   */
  async getUpstoxAuthUrl(userId: string): Promise<string> {
    const response = await fetch(`${API_BASE}/broker/upstox/auth-url?user_id=${userId}`);
    if (!response.ok) throw new Error('Failed to get Upstox auth URL from backend');
    const data = await response.json();
    return data.auth_url as string;
  }

  /**
   * Step 2 (called after OAuth callback): Exchange code for tokens.
   * The backend handles this at /broker/upstox/callback — Angular just
   * needs to know when it's done. Status is written to Firestore by backend.
   */
  async disconnectBroker(brokerAccountId: string): Promise<void> {
    // Tell backend to revoke token
    await fetch(`${API_BASE}/broker/disconnect/${brokerAccountId}`, { method: 'POST' });
    // Update Firestore status
    const ref = doc(this.firestore, `brokerAccounts/${brokerAccountId}`);
    await updateDoc(ref, {
      isConnected: false,
      lastRefreshedAt: serverTimestamp()
    });
  }

  async deleteBrokerAccount(brokerAccountId: string): Promise<void> {
    const ref = doc(this.firestore, `brokerAccounts/${brokerAccountId}`);
    await deleteDoc(ref);
  }
}
