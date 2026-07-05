import { Injectable, inject } from '@angular/core';
import {
  Firestore,
  collection,
  collectionData,
  doc,
  docData,
  updateDoc,
  query,
  orderBy,
  serverTimestamp
} from '@angular/fire/firestore';
import { Observable } from 'rxjs';
import { TradzoUser } from '../../models/user.model';

@Injectable({ providedIn: 'root' })
export class AdminService {
  private firestore = inject(Firestore);

  // ── Users ────────────────────────────────────────────────────────────────

  getAllUsers(): Observable<TradzoUser[]> {
    const ref = query(
      collection(this.firestore, 'users'),
      orderBy('createdAt', 'desc')
    );
    return collectionData(ref, { idField: 'uid' }) as Observable<TradzoUser[]>;
  }

  getUser(uid: string): Observable<TradzoUser> {
    const ref = doc(this.firestore, `users/${uid}`);
    return docData(ref, { idField: 'uid' }) as Observable<TradzoUser>;
  }

  async setAdminRole(uid: string, isAdmin: boolean): Promise<void> {
    const ref = doc(this.firestore, `users/${uid}`);
    await updateDoc(ref, { isAdmin, updatedAt: serverTimestamp() });
  }

  // ── Strategy management (admin overrides visible strategies) ─────────────

  async pauseUserStrategyByAdmin(userStrategyId: string): Promise<void> {
    const ref = doc(this.firestore, `userStrategies/${userStrategyId}`);
    await updateDoc(ref, {
      status: 'paused',
      pausedByAdmin: true,
      pausedAt: serverTimestamp()
    });
  }

  async resumeUserStrategyByAdmin(userStrategyId: string): Promise<void> {
    const ref = doc(this.firestore, `userStrategies/${userStrategyId}`);
    await updateDoc(ref, {
      status: 'active',
      pausedByAdmin: false,
      pausedAt: null
    });
  }
}
