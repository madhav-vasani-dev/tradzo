import { Injectable, inject } from '@angular/core';
import { Auth, onAuthStateChanged, User } from '@angular/fire/auth';
import { Firestore, doc, docData, setDoc } from '@angular/fire/firestore';
import { Observable, BehaviorSubject, of } from 'rxjs';
import { map } from 'rxjs/operators';
import { TradzoUser } from '../../models/user.model';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private auth = inject(Auth);
  private firestore = inject(Firestore);

  private _currentUser$ = new BehaviorSubject<TradzoUser | null>(null);
  readonly currentUser$ = this._currentUser$.asObservable();

  /** Reactive — emits true/false whenever user doc changes in Firestore */
  readonly isAdmin$ = this._currentUser$.pipe(
    map(u => !!(u?.isAdmin || u?.isSuperUser))
  );

  constructor() {
    onAuthStateChanged(this.auth, async (firebaseUser) => {
      if (firebaseUser) {
        const userRef = doc(this.firestore, `users/${firebaseUser.uid}`);
        docData(userRef).subscribe((data) => {
          this._currentUser$.next(data as TradzoUser ?? null);
        });
      } else {
        this._currentUser$.next(null);
      }
    });
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
