import { Injectable, inject } from '@angular/core';
import { Auth, onAuthStateChanged, User } from '@angular/fire/auth';
import { Firestore, doc, docData, setDoc } from '@angular/fire/firestore';
import { Observable, BehaviorSubject, from } from 'rxjs';
import { switchMap, map } from 'rxjs/operators';
import { TradzoUser } from '../../models/user.model';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private auth = inject(Auth);
  private firestore = inject(Firestore);

  private _currentUser$ = new BehaviorSubject<TradzoUser | null>(null);
  readonly currentUser$ = this._currentUser$.asObservable();

  constructor() {
    onAuthStateChanged(this.auth, async (firebaseUser) => {
      if (firebaseUser) {
        const userRef = doc(this.firestore, `users/${firebaseUser.uid}`);
        docData(userRef).subscribe({
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
