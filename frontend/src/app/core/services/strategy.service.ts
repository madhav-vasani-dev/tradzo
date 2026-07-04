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
import { Strategy, UserStrategy } from '../../models/strategy.model';

@Injectable({ providedIn: 'root' })
export class StrategyService {
  private firestore = inject(Firestore);

  // ── Public (user-facing) ──────────────────────────────────────────────────

  /** Returns only visible strategies for regular users */
  getVisibleStrategies(): Observable<Strategy[]> {
    const ref = query(
      collection(this.firestore, 'strategies'),
      where('isVisible', '==', true),
      orderBy('createdAt', 'desc')
    );
    return collectionData(ref, { idField: 'id' }) as Observable<Strategy[]>;
  }

  /** Returns a single strategy by ID */
  getStrategy(id: string): Observable<Strategy> {
    const ref = doc(this.firestore, `strategies/${id}`);
    return docData(ref, { idField: 'id' }) as Observable<Strategy>;
  }

  /** Returns all userStrategy deployments for a given user */
  getUserStrategies(userId: string): Observable<UserStrategy[]> {
    const ref = query(
      collection(this.firestore, 'userStrategies'),
      where('userId', '==', userId),
      orderBy('deployedAt', 'desc')
    );
    return collectionData(ref, { idField: 'id' }) as Observable<UserStrategy[]>;
  }

  /** Deploy a strategy for a user */
  async deployStrategy(
    userId: string,
    strategyId: string,
    strategyName: string,
    brokerAccountId: string,
    brokerName: 'upstox' | 'jainam',
    deployedAmount: number
  ): Promise<void> {
    const userStrategyRef = collection(this.firestore, 'userStrategies');
    await addDoc(userStrategyRef, {
      userId,
      strategyId,
      strategyName,
      brokerAccountId,
      brokerName,
      deployedAmount,
      status: 'active',
      deployedAt: serverTimestamp(),
      lastTradedAt: null,
      pausedAt: null,
      stoppedAt: null,
      pausedByAdmin: false
    });

    // Update user's deployedStrategyIds array via arrayUnion
    const { arrayUnion } = await import('@angular/fire/firestore');
    const userRef = doc(this.firestore, `users/${userId}`);
    await updateDoc(userRef, {
      deployedStrategyIds: arrayUnion(strategyId)
    });
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
    await updateDoc(ref, { status: 'active', pausedAt: null });
  }

  // ── Admin ─────────────────────────────────────────────────────────────────

  /** Returns ALL strategies (including hidden) — admin only */
  getAllStrategies(): Observable<Strategy[]> {
    const ref = query(
      collection(this.firestore, 'strategies'),
      orderBy('createdAt', 'desc')
    );
    return collectionData(ref, { idField: 'id' }) as Observable<Strategy[]>;
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
}
