import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DialogModule } from 'primeng/dialog';

/**
 * Confirmation dialog that owns running the action it confirms.
 *
 * The action lives here rather than in the caller so the busy state can't be skipped:
 * while it runs the confirm button is disabled and shows a spinner, and the dialog
 * refuses to close. Actions behind this dialog place real broker orders — a second
 * click during the few seconds a square-off takes used to fire a second set of orders.
 *
 * Callers pass `action` and handle the outcome via (succeeded) / (failed).
 */
@Component({
  selector: 'app-confirm-action-dialog',
  standalone: true,
  imports: [CommonModule, DialogModule],
  templateUrl: './confirm-action-dialog.component.html',
  styleUrl: './confirm-action-dialog.component.scss'
})
export class ConfirmActionDialogComponent {
  @Input() visible = false;
  @Output() visibleChange = new EventEmitter<boolean>();

  @Input() title = '';
  @Input() message = '';
  @Input() confirmText = 'Confirm';
  @Input() cancelText = 'Cancel';
  /** Text shown next to the spinner while the action runs. */
  @Input() runningText = 'Processing…';
  /** The work to perform on confirm. Awaited; the dialog stays open until it settles. */
  @Input() action: (() => Promise<unknown>) | null = null;

  @Output() succeeded = new EventEmitter<void>();
  @Output() failed = new EventEmitter<Error>();

  running = false;

  async confirm() {
    // Belt and braces: the button is disabled while running, and this rejects any
    // click that still gets through (rapid double-click, keyboard repeat, replayed event).
    if (this.running || !this.action) return;

    this.running = true;
    try {
      await this.action();
      this.close();
      this.succeeded.emit();
    } catch (err: any) {
      this.close();
      this.failed.emit(err instanceof Error ? err : new Error(err?.message || 'An error occurred.'));
    } finally {
      this.running = false;
    }
  }

  /** Cancelling mid-run is not offered — the order is already on its way to the broker. */
  cancel() {
    if (this.running) return;
    this.close();
  }

  onVisibleChange(value: boolean) {
    if (!value && this.running) return;   // block Escape / mask / X while running
    this.visible = value;
    this.visibleChange.emit(value);
  }

  private close() {
    this.visible = false;
    this.visibleChange.emit(false);
  }
}
