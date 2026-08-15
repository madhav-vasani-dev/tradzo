import { Injectable, signal, inject } from '@angular/core';
import { SwUpdate, VersionReadyEvent } from '@angular/service-worker';
import { filter } from 'rxjs/operators';

export interface BeforeInstallPromptEvent extends Event {
  readonly platforms: string[];
  readonly userChoice: Promise<{
    outcome: 'accepted' | 'dismissed';
    platform: string;
  }>;
  prompt(): Promise<void>;
}

@Injectable({
  providedIn: 'root'
})
export class PwaService {
  private swUpdate = inject(SwUpdate, { optional: true });
  private deferredPrompt: BeforeInstallPromptEvent | null = null;

  public canInstall = signal<boolean>(false);
  public updateAvailable = signal<boolean>(false);
  public isInstalled = signal<boolean>(false);

  constructor() {
    this.initPwaListeners();
    this.initSwUpdate();
  }

  private initPwaListeners(): void {
    // Check if app is already running in standalone mode (PWA installed)
    if (window.matchMedia('(display-mode: standalone)').matches || (navigator as any).standalone) {
      this.isInstalled.set(true);
    }

    // Capture install prompt event
    window.addEventListener('beforeinstallprompt', (e: Event) => {
      e.preventDefault();
      this.deferredPrompt = e as BeforeInstallPromptEvent;
      this.canInstall.set(true);
    });

    // Capture appinstalled event
    window.addEventListener('appinstalled', () => {
      this.deferredPrompt = null;
      this.canInstall.set(false);
      this.isInstalled.set(true);
      console.log('Tradzo PWA was successfully installed.');
    });
  }

  private initSwUpdate(): void {
    if (!this.swUpdate || !this.swUpdate.isEnabled) return;

    this.swUpdate.versionUpdates
      .pipe(filter((evt): evt is VersionReadyEvent => evt.type === 'VERSION_READY'))
      .subscribe(() => {
        this.updateAvailable.set(true);
      });
  }

  public async promptInstall(): Promise<boolean> {
    if (!this.deferredPrompt) {
      return false;
    }

    try {
      await this.deferredPrompt.prompt();
      const choiceResult = await this.deferredPrompt.userChoice;
      
      if (choiceResult.outcome === 'accepted') {
        this.canInstall.set(false);
        this.deferredPrompt = null;
        return true;
      }
    } catch (err) {
      console.error('Error prompting PWA install:', err);
    }

    return false;
  }

  public reloadToUpdate(): void {
    if (this.swUpdate) {
      this.swUpdate.activateUpdate().then(() => document.location.reload());
    }
  }
}
