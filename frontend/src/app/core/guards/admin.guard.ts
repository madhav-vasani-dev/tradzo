import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { Auth } from '@angular/fire/auth';
import { Firestore, doc, getDoc } from '@angular/fire/firestore';

export const adminGuard: CanActivateFn = async (route, state) => {
  const auth = inject(Auth);
  const firestore = inject(Firestore);
  const router = inject(Router);

  await auth.authStateReady();
  const user = auth.currentUser;

  if (!user) {
    router.navigate(['/auth']);
    return false;
  }

  try {
    const userDoc = await getDoc(doc(firestore, `users/${user.uid}`));
    if (!userDoc.exists()) {
      router.navigate(['/strategies']);
      return false;
    }

    const data = userDoc.data() as any;
    if (!!data?.isAdmin || !!data?.isSuperUser) {
      return true;
    }
    router.navigate(['/strategies']);
    return false;
  } catch {
    router.navigate(['/strategies']);
    return false;
  }
};
