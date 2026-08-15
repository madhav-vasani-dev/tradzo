import { ApplicationConfig, provideZoneChangeDetection, isDevMode } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideServiceWorker } from '@angular/service-worker';
import { providePrimeNG } from 'primeng/config';
import Aura from '@primeuix/themes/aura';
import { MessageService } from 'primeng/api';
import { routes } from './app.routes';
import { errorDetailInterceptor } from './core/interceptors/error-detail.interceptor';

import { provideFirebaseApp, initializeApp, getApp } from '@angular/fire/app';
import { provideAuth, getAuth } from '@angular/fire/auth';
import { provideFirestore, initializeFirestore } from '@angular/fire/firestore';


const firebaseConfig = {
  apiKey: "AIzaSyBHMdQ54FCXSOhsZ47wQwvEKeWIAaZ7D7M",
  authDomain: "algo-trading-a70a5.firebaseapp.com",
  databaseURL: "https://algo-trading-a70a5-default-rtdb.firebaseio.com",
  projectId: "algo-trading-a70a5",
  storageBucket: "algo-trading-a70a5.firebasestorage.app",
  messagingSenderId: "43784514677",
  appId: "1:43784514677:web:3a60e51d4b1c907437dc3c",
  measurementId: "G-D0T1HQE33B"
};

export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes),
    provideAnimationsAsync(),
    provideHttpClient(withInterceptors([errorDetailInterceptor])),
    provideServiceWorker('ngsw-worker.js', {
      enabled: !isDevMode(),
      registrationStrategy: 'registerWhenStable:30000'
    }),
    providePrimeNG({
      theme: {
        preset: Aura,
        options: {
          darkModeSelector: 'body',
          cssLayer: false
        }
      }
    }),
    MessageService,
    provideFirebaseApp(() => initializeApp(firebaseConfig)),
    provideAuth(() => getAuth()),
    // Auto-detect long polling: avoids the ~10-15s stall when a network/proxy
    // blocks Firestore's WebChannel streaming connection (common cause of slow
    // first queries, e.g. on the Broker Accounts page).
    provideFirestore(() => initializeFirestore(getApp(), {
      experimentalAutoDetectLongPolling: true,
    }))
  ]
};
