import { Injectable, Injector, inject, runInInjectionContext } from '@angular/core';
import { Auth, onAuthStateChanged, User } from '@angular/fire/auth';
import { Firestore, doc, docData, getDoc, setDoc, serverTimestamp } from '@angular/fire/firestore';
import { Observable, BehaviorSubject, of } from 'rxjs';
import { map } from 'rxjs/operators';
import { TradzoUser } from '../../models/user.model';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private auth = inject(Auth);
  private firestore = inject(Firestore);
  private injector = inject(Injector);

  private _currentUser$ = new BehaviorSubject<TradzoUser | null>(null);
  readonly currentUser$ = this._currentUser$.asObservable();

  /** Reactive — emits true/false whenever user doc changes in Firestore */
  readonly isAdmin$ = this._currentUser$.pipe(
    map(u => !!(u?.isAdmin || u?.isSuperUser))
  );

  readonly isSuperUser$ = this._currentUser$.pipe(
    map(u => !!u?.isSuperUser)
  );

  constructor() {
    onAuthStateChanged(this.auth, async (firebaseUser) => {
      if (firebaseUser) {
        // Guarantee every authenticated user has a Firestore record, so they
        // show up in the admin Users list regardless of sign-in method
        // (email signup, Google, etc.).
        await this.ensureUserDoc(firebaseUser);

        // Keep the live user-doc stream inside the injection context/zone so
        // currentUser$ (and the sidebar's isAdmin$) update via change detection.
        const userDoc$ = runInInjectionContext(this.injector, () => {
          const userRef = doc(this.firestore, `users/${firebaseUser.uid}`);
          return docData(userRef);
        });
        userDoc$.subscribe({
          next: (data) => {
            this._currentUser$.next(data as TradzoUser ?? null);
          },
          error: () => {
            this._currentUser$.next(null);
          }
        });
      } else {
        this._currentUser$.next(null);
      }
    });
  }

  /**
   * Create a `users/{uid}` document with sane defaults if one doesn't exist.
   * Only writes when the doc is missing, so it never clobbers an existing
   * user's isAdmin/isSuperUser flags.
   */
  private async ensureUserDoc(fbUser: User): Promise<void> {
    const userRef = doc(this.firestore, `users/${fbUser.uid}`);
    try {
      const snap = await runInInjectionContext(this.injector, () => getDoc(userRef));
      if (snap.exists()) return;

      const username =
        fbUser.displayName || (fbUser.email ? fbUser.email.split('@')[0] : 'User');
      await runInInjectionContext(this.injector, () => setDoc(userRef, {
        uid: fbUser.uid,
        username,
        email: fbUser.email ?? '',
        photoURL: fbUser.photoURL ?? null,
        isAdmin: false,
        isSuperUser: false,
        createdAt: serverTimestamp(),
        deployedStrategyIds: [],
        brokerConnected: false,
      }));
    } catch {
      // Best-effort — a rules/permission error here shouldn't block sign-in.
    }
  }

  get currentUser(): TradzoUser | null {
    return this._currentUser$.getValue();
  }

  get isAdmin(): boolean {
    const u = this._currentUser$.getValue();
    return !!(u?.isAdmin || u?.isSuperUser);
  }

  get isSuperUser(): boolean {
    return !!this._currentUser$.getValue()?.isSuperUser;
  }
}
