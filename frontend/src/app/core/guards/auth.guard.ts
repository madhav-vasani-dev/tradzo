import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { Auth } from '@angular/fire/auth';

export const authGuard: CanActivateFn = async (route, state) => {
  const auth = inject(Auth);
  const router = inject(Router);

  // Resolves as soon as Firebase has determined the initial auth state.
  // After the first load this returns immediately, so navigation isn't blocked
  // on a fresh auth listener each time.
  await auth.authStateReady();

  const user = auth.currentUser;
  if (!user) {
    router.navigate(['/auth']);
    return false;
  }

  const expiry = localStorage.getItem('sessionExpiry');
  if (expiry && Date.now() > parseInt(expiry, 10)) {
    await auth.signOut();
    localStorage.removeItem('sessionExpiry');
    router.navigate(['/auth']);
    return false;
  }

  return true;
};
