import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ButtonModule } from 'primeng/button';
import { PwaService } from '../../../core/services/pwa.service';

@Component({
  selector: 'app-pwa-install-prompt',
  standalone: true,
  imports: [CommonModule, ButtonModule],
  templateUrl: './pwa-install-prompt.component.html',
  styleUrl: './pwa-install-prompt.component.scss'
})
export class PwaInstallPromptComponent {
  public pwaService = inject(PwaService);
  public isDismissed = signal<boolean>(false);

  public installApp(): void {
    this.pwaService.promptInstall();
  }

  public dismiss(): void {
    this.isDismissed.set(true);
  }
}
