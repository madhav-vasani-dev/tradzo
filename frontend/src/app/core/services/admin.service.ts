import { Injectable, Injector, inject, runInInjectionContext } from '@angular/core';
import {
  Firestore,
  collection,
  collectionData,
  doc,
  docData,
  updateDoc,
  serverTimestamp,
  query,
  where,
  orderBy
} from '@angular/fire/firestore';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import { Auth } from '@angular/fire/auth';
import { TradzoUser } from '../../models/user.model';

@Injectable({ providedIn: 'root' })
export class AdminService {
  private firestore = inject(Firestore);
  private injector = inject(Injector);
  private auth = inject(Auth);

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
        map(users => (users || []).map(u => ({
          ...u,
          deployedStrategyIds: u.deployedStrategyIds || []
        })).sort((a, b) => this.createdMillis(b) - this.createdMillis(a)))
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
      status: 'enabled',
      pausedByAdmin: false,
      pausedAt: null
    });
  }

  // ── Activity Logs & Trading Mode (Phase 2 updates) ───────────────────────

  /** Get real-time activity logs for a specific date (defaults to today) */
  getActivityLogs(dateStr?: string): Observable<any[]> {
    const today = dateStr || new Date().toISOString().split('T')[0];
    return runInInjectionContext(this.injector, () => {
      const ref = collection(this.firestore, 'activityLogs');
      return (collectionData(ref, { idField: 'id' }) as Observable<any[]>).pipe(
        map(logs => [...logs]
          .filter(l => l.date === today)
          .sort((a, b) => this.createdMillisForLog(a) - this.createdMillisForLog(b))
        )
      );
    });
  }

  private createdMillisForLog(log: any): number {
    const ts: any = log.createdAt;
    if (!ts) return 0;
    if (typeof ts.toMillis === 'function') return ts.toMillis();
    if (typeof ts.seconds === 'number') return ts.seconds * 1000;
    const parsed = Date.parse(ts);
    return isNaN(parsed) ? 0 : parsed;
  }

  async toggleTradingMode(paper: boolean, userId: string, userName: string): Promise<void> {
    const { BACKEND_BASE_URL } = await import('../config');
    const token = await this.auth.currentUser?.getIdToken();
    const response = await fetch(`${BACKEND_BASE_URL}/execution/trading-mode`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        paperTrading: paper,
        userId: userId,
        userName: userName
      })
    });
    if (!response.ok) {
      let detail = 'Failed to toggle trading mode.';
      try {
        const err = await response.json();
        if (err?.detail) detail = typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail);
      } catch { /* ignore */ }
      throw new Error(detail);
    }
  }
}

