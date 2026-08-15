import { Injectable } from '@angular/core';

interface CacheEntry {
  data: any;
  expiry: number;
}

@Injectable({ providedIn: 'root' })
export class ApiCacheService {
  private cache = new Map<string, CacheEntry>();

  /** Default TTL in milliseconds for specific API endpoint patterns */
  private readonly DEFAULT_TTLS: Array<{ pattern: RegExp; ttlMs: number }> = [
    { pattern: /\/seasonality\/stocks/, ttlMs: 15 * 60 * 1000 },          // 15 minutes
    { pattern: /\/seasonality\/trade-scanner/, ttlMs: 10 * 60 * 1000 },   // 10 minutes
    { pattern: /\/seasonality\/upcoming-trades/, ttlMs: 10 * 60 * 1000 }, // 10 minutes
    { pattern: /\/seasonality\/cached-results/, ttlMs: 10 * 60 * 1000 },  // 10 minutes
    { pattern: /\/strategies/, ttlMs: 5 * 60 * 1000 },                    // 5 minutes
    { pattern: /\/users/, ttlMs: 2 * 60 * 1000 },                         // 2 minutes
  ];

  /** Get default TTL for a URL, defaulting to 5 minutes */
  getTtlForUrl(url: string): number {
    for (const rule of this.DEFAULT_TTLS) {
      if (rule.pattern.test(url)) {
        return rule.ttlMs;
      }
    }
    return 5 * 60 * 1000; // 5 minutes fallback
  }

  get(key: string): any | null {
    const entry = this.cache.get(key);
    if (!entry) return null;

    if (Date.now() > entry.expiry) {
      this.cache.delete(key);
      return null;
    }

    return entry.data;
  }

  set(key: string, data: any, ttlMs?: number): void {
    const timeToLive = ttlMs ?? this.getTtlForUrl(key);
    this.cache.set(key, {
      data,
      expiry: Date.now() + timeToLive,
    });
  }

  /** Invalidate specific endpoint pattern or all cache */
  clear(urlPattern?: string): void {
    if (!urlPattern) {
      this.cache.clear();
      return;
    }
    const regex = new RegExp(urlPattern);
    for (const key of this.cache.keys()) {
      if (regex.test(key)) {
        this.cache.delete(key);
      }
    }
  }
}
