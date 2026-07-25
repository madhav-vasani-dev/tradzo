import { Injectable, inject } from '@angular/core';
import {
  Firestore,
  collection,
  collectionData,
  doc,
  docData,
  addDoc,
  setDoc,
  updateDoc,
  deleteDoc,
  query,
  where,
  orderBy,
  serverTimestamp
} from '@angular/fire/firestore';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import { Strategy, UserStrategy, Position } from '../../models/strategy.model';
import { BrokerName } from '../../models/broker-account.model';
import { BACKEND_BASE_URL } from '../config';
import { Auth } from '@angular/fire/auth';


@Injectable({ providedIn: 'root' })
export class StrategyService {
  private firestore = inject(Firestore);
  private auth = inject(Auth);

  // ── Public (user-facing) ──────────────────────────────────────────────────

  /** Returns only visible strategies for regular users */
  getVisibleStrategies(): Observable<Strategy[]> {
    const ref = collection(this.firestore, 'strategies');
    return (collectionData(ref, { idField: 'id' }) as Observable<Strategy[]>).pipe(
      map(strategies => [...strategies]
        .filter(s => s.isVisible)
        .sort((a, b) => this.createdMillis(b) - this.createdMillis(a))
      )
    );
  }

  /** Returns a single strategy by ID */
  getStrategy(id: string): Observable<Strategy> {
    const ref = doc(this.firestore, `strategies/${id}`);
    return docData(ref, { idField: 'id' }) as Observable<Strategy>;
  }

  /** Returns all userStrategy deployments for a given user */
  getUserStrategies(userId: string): Observable<UserStrategy[]> {
    const ref = collection(this.firestore, 'userStrategies');
    const q = query(ref, where('userId', '==', userId));
    return (collectionData(q, { idField: 'id' }) as Observable<UserStrategy[]>).pipe(
      map(userStrats => [...userStrats]
        .sort((a, b) => this.deployedMillis(b) - this.deployedMillis(a))
      )
    );
  }

  /** Deploy a strategy for a user */
  async deployStrategy(
    userId: string,
    strategyId: string,
    strategyCode: string,
    strategyName: string,
    brokerAccountId: string,
    brokerName: BrokerName,
    deployedAmount: number,
    multiplier: number,
  ): Promise<void> {
    const userStrategyRef = collection(this.firestore, 'userStrategies');
    await addDoc(userStrategyRef, {
      userId,
      strategyId,
      strategyCode,
      strategyName,
      brokerAccountId,
      brokerName,
      deployedAmount,
      multiplier,
      status: 'enabled',
      statusUpdatedAt: serverTimestamp(),
      deployedAt: serverTimestamp(),
      pausedByAdmin: false,
    });

    // Update user's deployedStrategyIds array via arrayUnion
    const { arrayUnion } = await import('@angular/fire/firestore');
    const userRef = doc(this.firestore, `users/${userId}`);
    await updateDoc(userRef, {
      deployedStrategyIds: arrayUnion(strategyId)
    });
  }

  /** Get real-time paper trading mode from settings/tradingMode */
  getTradingMode(): Observable<{ paperTrading: boolean; updatedByName?: string }> {
    const ref = doc(this.firestore, 'settings/tradingMode');
    return docData(ref) as Observable<{ paperTrading: boolean; updatedByName?: string }>;
  }

  /** Get all positions for a user on a specific date (defaults to today) */
  getUserPositions(userId: string, dateStr?: string): Observable<Position[]> {
    const today = dateStr || new Date().toISOString().split('T')[0];
    const ref = collection(this.firestore, 'positions');
    const q = query(ref, where('userId', '==', userId), where('date', '==', today));
    return (collectionData(q, { idField: 'id' }) as Observable<Position[]>).pipe(
      map(positions => [...positions]
        .sort((a, b) => this.entryMillis(a) - this.entryMillis(b))
      )
    );
  }

  private deployedMillis(us: UserStrategy): number {
    const ts: any = us.deployedAt;
    if (!ts) return 0;
    if (typeof ts.toMillis === 'function') return ts.toMillis();
    if (typeof ts.seconds === 'number') return ts.seconds * 1000;
    const parsed = Date.parse(ts);
    return isNaN(parsed) ? 0 : parsed;
  }

  private entryMillis(p: Position): number {
    const ts: any = p.entryAt;
    if (!ts) return 0;
    if (typeof ts.toMillis === 'function') return ts.toMillis();
    if (typeof ts.seconds === 'number') return ts.seconds * 1000;
    const parsed = Date.parse(ts);
    return isNaN(parsed) ? 0 : parsed;
  }


  /** Pause a user's strategy deployment */
  async pauseUserStrategy(userStrategyId: string): Promise<void> {
    const ref = doc(this.firestore, `userStrategies/${userStrategyId}`);
    await updateDoc(ref, { status: 'paused', pausedAt: serverTimestamp(), pausedByAdmin: false });
  }

  /** Stop a user's strategy deployment */
  async stopUserStrategy(userStrategyId: string): Promise<void> {
    const ref = doc(this.firestore, `userStrategies/${userStrategyId}`);
    await updateDoc(ref, { status: 'stopped', stoppedAt: serverTimestamp() });
  }

  /** Resume a paused deployment */
  async resumeUserStrategy(userStrategyId: string): Promise<void> {
    const ref = doc(this.firestore, `userStrategies/${userStrategyId}`);
    await updateDoc(ref, { status: 'enabled', pausedAt: null });
  }

  /** Stop a user's strategy deployment for today only */
  async disableStrategyForToday(userStrategyId: string): Promise<void> {
    const ref = doc(this.firestore, `userStrategies/${userStrategyId}`);
    await updateDoc(ref, { status: 'disabled_today' });
  }

  /** Square off positions and stop strategy for today */
  async squareOffUserStrategy(userStrategyId: string): Promise<any> {
    const token = await this.auth.currentUser?.getIdToken();
    const response = await fetch(`${BACKEND_BASE_URL}/execution/square-off/${userStrategyId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      }
    });
    if (!response.ok) {
      const data = await response.json();
      throw new Error(data?.detail || 'Failed to square off strategy.');
    }
    return response.json();
  }


  // ── Admin ─────────────────────────────────────────────────────────────────

  /** Returns ALL strategies (including hidden) — admin only */
  getAllStrategies(): Observable<Strategy[]> {
    const ref = collection(this.firestore, 'strategies');
    return (collectionData(ref, { idField: 'id' }) as Observable<Strategy[]>).pipe(
      map(strategies => [...strategies].sort((a, b) => this.createdMillis(b) - this.createdMillis(a)))
    );
  }

  /** Best-effort ms-since-epoch from a Firestore Timestamp, ISO string, or nothing. */
  private createdMillis(s: Strategy): number {
    const ts: any = s.createdAt;
    if (!ts) return 0;
    if (typeof ts.toMillis === 'function') return ts.toMillis();
    if (typeof ts.seconds === 'number') return ts.seconds * 1000;
    const parsed = Date.parse(ts);
    return isNaN(parsed) ? 0 : parsed;
  }

  /** Create a new strategy */
  async createStrategy(strategy: Omit<Strategy, 'id' | 'createdAt' | 'updatedAt'>): Promise<void> {
    const ref = collection(this.firestore, 'strategies');
    await addDoc(ref, {
      ...strategy,
      createdAt: serverTimestamp(),
      updatedAt: serverTimestamp()
    });
  }

  /** Update an existing strategy */
  async updateStrategy(id: string, data: Partial<Strategy>): Promise<void> {
    const ref = doc(this.firestore, `strategies/${id}`);
    await updateDoc(ref, { ...data, updatedAt: serverTimestamp() });
  }

  /** Toggle visibility */
  async toggleVisibility(id: string, isVisible: boolean): Promise<void> {
    const ref = doc(this.firestore, `strategies/${id}`);
    await updateDoc(ref, { isVisible, updatedAt: serverTimestamp() });
  }

  /** Delete a strategy */
  async deleteStrategy(id: string): Promise<void> {
    const ref = doc(this.firestore, `strategies/${id}`);
    await deleteDoc(ref);
  }

  /** Get P&L report for a user, strategy, and date range */
  async getPnlReport(
    userId?: string,
    strategyId?: string,
    startDate?: string,
    endDate?: string
  ): Promise<any> {
    const params = new URLSearchParams();
    if (userId) params.append('userId', userId);
    if (strategyId) params.append('strategyId', strategyId);
    if (startDate) params.append('startDate', startDate);
    if (endDate) params.append('endDate', endDate);

    const token = await this.auth.currentUser?.getIdToken();
    const response = await fetch(`${BACKEND_BASE_URL}/execution/pnl?${params.toString()}`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    if (!response.ok) {
      const data = await response.json();
      throw new Error(data?.detail || 'Failed to fetch P&L report.');
    }
    return response.json();
  }

  /** Stream simulated (system/paper) positions for a strategy */
  getStrategySimulatedTrades(strategyId: string): Observable<any[]> {
    const ref = query(
      collection(this.firestore, 'positions'),
      where('strategyId', '==', strategyId),
      where('isPaper', '==', true)
    );
    return collectionData(ref, { idField: 'id' }) as Observable<any[]>;
  }
}
