import { Injectable, Injector, inject, runInInjectionContext } from '@angular/core';
import {
  Firestore,
  collection,
  collectionData,
  doc,
  docData,
  updateDoc,
  serverTimestamp
} from '@angular/fire/firestore';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import { TradzoUser } from '../../models/user.model';

@Injectable({ providedIn: 'root' })
export class AdminService {
  private firestore = inject(Firestore);
  private injector = inject(Injector);

  // ── Users ────────────────────────────────────────────────────────────────

  /**
   * Every user in the app. We deliberately do NOT use a Firestore `orderBy`
   * here: Firestore omits any document missing the ordered field, which would
   * silently hide users whose doc has no `createdAt`. Instead we fetch all docs
   * and sort newest-first in-app (tolerating missing/mixed timestamp types).
   *
   * runInInjectionContext: called from a component's ngOnInit, so we must keep
   * AngularFire in the injection context/zone or emissions miss change detection.
   */
  getAllUsers(): Observable<TradzoUser[]> {
    return runInInjectionContext(this.injector, () => {
      const ref = collection(this.firestore, 'users');
      return (collectionData(ref, { idField: 'uid' }) as Observable<TradzoUser[]>).pipe(
        map(users => [...users].sort((a, b) => this.createdMillis(b) - this.createdMillis(a)))
      );
    });
  }

  /** Best-effort ms-since-epoch from a Firestore Timestamp, ISO string, or nothing. */
  private createdMillis(u: TradzoUser): number {
    const ts: any = (u as any).createdAt;
    if (!ts) return 0;
    if (typeof ts.toMillis === 'function') return ts.toMillis();
    if (typeof ts.seconds === 'number') return ts.seconds * 1000;
    const parsed = Date.parse(ts);
    return isNaN(parsed) ? 0 : parsed;
  }

  getUser(uid: string): Observable<TradzoUser> {
    return runInInjectionContext(this.injector, () => {
      const ref = doc(this.firestore, `users/${uid}`);
      return docData(ref, { idField: 'uid' }) as Observable<TradzoUser>;
    });
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
