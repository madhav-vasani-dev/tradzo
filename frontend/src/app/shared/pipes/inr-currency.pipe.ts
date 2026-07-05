import { Pipe, PipeTransform } from '@angular/core';

@Pipe({ name: 'inrCurrency', standalone: true })
export class InrCurrencyPipe implements PipeTransform {
  transform(value: number, showSymbol = true): string {
    const formatted = new Intl.NumberFormat('en-IN', {
      maximumFractionDigits: 0
    }).format(value);
    return showSymbol ? `₹${formatted}` : formatted;
  }
}
