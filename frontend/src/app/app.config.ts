import { ApplicationConfig, provideZoneChangeDetection } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';
import { provideHttpClient } from '@angular/common/http';
import { providePrimeNG } from 'primeng/config';
import Aura from '@primeuix/themes/aura';
import { MessageService } from 'primeng/api';
import { routes } from './app.routes';

import { provideFirebaseApp, initializeApp } from '@angular/fire/app';
import { provideAuth, getAuth } from '@angular/fire/auth';
import { provideFirestore, getFirestore } from '@angular/fire/firestore';


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
    provideHttpClient(),
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
    provideFirestore(() => getFirestore())
  ]
};
