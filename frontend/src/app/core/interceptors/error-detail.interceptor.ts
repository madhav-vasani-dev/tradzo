import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { throwError } from 'rxjs';
import { catchError } from 'rxjs/operators';

/**
 * FastAPI error responses carry the real reason in `{ detail: "..." }`, but
 * HttpErrorResponse.message is always a generic "Http failure response ... 400
 * Bad Request" string — every `catch (err) { ... err.message }` call site in
 * this app was silently losing the backend's actual message. Unwrap it once,
 * here, instead of fixing every caller individually.
 */
export const errorDetailInterceptor: HttpInterceptorFn = (req, next) =>
  next(req).pipe(
    catchError((err: unknown) => {
      if (err instanceof HttpErrorResponse) {
        const detail = err.error?.detail;
        if (typeof detail === 'string' && detail) {
          // .message is readonly per Angular's type — harmless to override at runtime, TS just needs convincing.
          (err as any).message = detail;
        }
      }
      return throwError(() => err);
    })
  );
