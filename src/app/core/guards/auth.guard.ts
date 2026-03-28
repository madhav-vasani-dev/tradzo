import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { Auth, onAuthStateChanged } from '@angular/fire/auth';

export const authGuard: CanActivateFn = (route, state) => {
  const auth = inject(Auth);
  const router = inject(Router);

  return new Promise((resolve) => {
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      unsubscribe();
      
      if (user) {
        const expiry = localStorage.getItem('sessionExpiry');
        if (expiry && Date.now() > parseInt(expiry, 10)) {
          auth.signOut().then(() => {
            localStorage.removeItem('sessionExpiry');
            router.navigate(['/auth']);
            resolve(false);
          });
        } else {
          resolve(true);
        }
      } else {
        router.navigate(['/auth']);
        resolve(false);
      }
    });
  });
};
