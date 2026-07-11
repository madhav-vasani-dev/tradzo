import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { Auth, onAuthStateChanged } from '@angular/fire/auth';
import { Firestore, doc, getDoc } from '@angular/fire/firestore';

export const adminGuard: CanActivateFn = async (route, state) => {
  const auth = inject(Auth);
  const firestore = inject(Firestore);
  const router = inject(Router);

  return new Promise((resolve) => {
    const unsubscribe = onAuthStateChanged(auth, async (user) => {
      unsubscribe();

      if (!user) {
        router.navigate(['/auth']);
        return resolve(false);
      }

      try {
        const userDoc = await getDoc(doc(firestore, `users/${user.uid}`));

        if (!userDoc.exists()) {
          router.navigate(['/strategies']);
          return resolve(false);
        }

        const data = userDoc.data() as any;

        if (!!data?.isAdmin || !!data?.isSuperUser) {
          return resolve(true);
        } else {
          router.navigate(['/strategies']);
          return resolve(false);
        }
      } catch (err) {
        router.navigate(['/strategies']);
        return resolve(false);
      }
    });
  });
};
