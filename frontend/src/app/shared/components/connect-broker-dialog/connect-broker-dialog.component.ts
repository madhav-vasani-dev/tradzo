import { Component, Input, Output, EventEmitter, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DialogModule } from 'primeng/dialog';
import { Auth } from '@angular/fire/auth';
import { BrokerService } from '../../../core/services/broker.service';
import { BrokerMeta } from '../../../models/broker-account.model';
import { BACKEND_BASE_URL } from '../../../core/config';

@Component({
  selector: 'app-connect-broker-dialog',
  standalone: true,
  imports: [CommonModule, FormsModule, DialogModule],
  templateUrl: './connect-broker-dialog.component.html',
  styleUrl: './connect-broker-dialog.component.scss'
})
export class ConnectBrokerDialogComponent {
  @Input() visible = false;
  @Input() meta: BrokerMeta | null = null;
  @Output() visibleChange = new EventEmitter<boolean>();
  /** Emitted after a synchronous (session) broker connects, so the parent reloads. */
  @Output() connected = new EventEmitter<void>();

  private auth = inject(Auth);
  private brokerService = inject(BrokerService);

  /** Field key -> entered value. */
  values: Record<string, string> = {};
  revealed: Record<string, boolean> = {};
  submitting = false;
  errorMessage = '';
  copiedPath: string | null = null;

  /** Reset state whenever the dialog is (re)opened for a broker. */
  onShow() {
    this.values = {};
    this.revealed = {};
    this.errorMessage = '';
    this.submitting = false;
    this.copiedPath = null;
  }

  /** Full URL a user registers in their broker app (backend base + path). */
  fullUrl(path: string): string {
    return `${BACKEND_BASE_URL}${path}`;
  }

  async copyUrl(path: string) {
    try {
      await navigator.clipboard.writeText(this.fullUrl(path));
      this.copiedPath = path;
      setTimeout(() => { if (this.copiedPath === path) this.copiedPath = null; }, 1800);
    } catch {
      // Clipboard blocked (e.g. non-HTTPS/older browser) — user can select manually.
    }
  }

  isValid(): boolean {
    if (!this.meta) return false;
    return this.meta.credentialFields
      .filter(f => f.required !== false)
      .every(f => (this.values[f.key] ?? '').trim().length > 0);
  }

  toggleReveal(key: string) {
    this.revealed[key] = !this.revealed[key];
  }

  async submit() {
    if (!this.meta || !this.isValid() || this.submitting) return;
    const user = this.auth.currentUser;
    if (!user) {
      this.errorMessage = 'You must be logged in to connect a broker.';
      return;
    }

    this.submitting = true;
    this.errorMessage = '';

    // Only send fields that have a value (optional keys may be blank).
    const creds: Record<string, string> = {};
    for (const f of this.meta.credentialFields) {
      const v = (this.values[f.key] ?? '').trim();
      if (v) creds[f.key] = v;
    }

    try {
      const res = await this.brokerService.connectBroker(this.meta.name, user.uid, creds);
      if (res.auth_url) {
        // OAuth broker (Upstox): hand off to the broker's login page.
        window.location.href = res.auth_url;
        return;
      }
      // Session broker (Jainam): connected synchronously.
      this.connected.emit();
      this.close();
    } catch (err: any) {
      this.errorMessage = err?.message || 'Could not connect. Please check your keys and try again.';
      this.submitting = false;
    }
  }

  close() {
    this.submitting = false;
    this.visibleChange.emit(false);
  }
}
