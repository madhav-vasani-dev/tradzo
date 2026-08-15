import { HttpInterceptorFn, HttpResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { of, tap } from 'rxjs';
import { ApiCacheService } from '../services/api-cache.service';

export const cacheInterceptor: HttpInterceptorFn = (req, next) => {
  // Only cache GET requests
  if (req.method !== 'GET') {
    return next(req);
  }

  // Allow explicit bypass via header
  if (req.headers.has('X-Bypass-Cache')) {
    const cleanReq = req.clone({ headers: req.headers.delete('X-Bypass-Cache') });
    return next(cleanReq);
  }

  const cacheService = inject(ApiCacheService);
  const cacheKey = req.urlWithParams;

  const cachedResponseData = cacheService.get(cacheKey);
  if (cachedResponseData !== null) {
    return of(new HttpResponse({ status: 200, body: cachedResponseData }));
  }

  return next(req).pipe(
    tap(event => {
      if (event instanceof HttpResponse && event.status === 200) {
        const customTtlHeader = req.headers.get('X-Cache-TTL');
        const customTtl = customTtlHeader ? parseInt(customTtlHeader, 10) : undefined;
        cacheService.set(cacheKey, event.body, customTtl);
      }
    })
  );
};
