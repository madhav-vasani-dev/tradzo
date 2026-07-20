/** Base URL of the Python (FastAPI) backend. */
export const BACKEND_BASE_URL = typeof window !== 'undefined' && 
  (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
    ? 'http://localhost:8000'
    : 'https://tradzo-backend.duckdns.org';
