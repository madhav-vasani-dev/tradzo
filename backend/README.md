# Tradzo Backend (Python / FastAPI)

Phase 1 backend for Tradzo: Upstox OAuth, secure token storage, morning strategy
execution (APScheduler), and Firestore writes via the Firebase Admin SDK.

## Setup

```bash
cd backend
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env        # then edit .env
```

Fill in `.env`:

1. **Upstox** — create an app at https://developer.upstox.com, set the redirect
   URI to `http://localhost:8000/broker/upstox/callback`, and copy the API
   key/secret into `UPSTOX_CLIENT_ID` / `UPSTOX_CLIENT_SECRET`.
2. **Firebase** — download a service-account key (Firebase Console → Project
   settings → Service accounts → Generate new private key), save it as
   `backend/firebase-service-account.json`, and point
   `FIREBASE_CREDENTIALS_PATH` at it.
3. **Token encryption** — generate a key and paste it into `TOKEN_ENCRYPTION_KEY`:
   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

## Run

```bash
uvicorn main:app --reload --port 8000
```

- Interactive API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

The API boots even without Firebase/Upstox configured (so `/health` works), but
Firestore-backed endpoints will error until credentials are set.

## Endpoints

| Method | Path | Body / Query | Purpose |
|---|---|---|---|
| GET | `/health` | — | Liveness + Firestore status |
| POST | `/broker/upstox/connect` | `{userId, apiKey, apiSecret}` | Start Upstox OAuth with the user's own app key; returns `{auth_url}` |
| GET | `/broker/upstox/callback` | `?code=&state=` | OAuth return; exchanges code, redirects to frontend |
| POST | `/broker/jainam/connect` | `{userId, interactiveApiKey, interactiveApiSecret, marketDataApiKey?, marketDataApiSecret?}` | Log in to Jainam XTS, store session; no redirect |
| POST | `/broker/disconnect/{account_id}` | — | Revoke token + credentials, mark disconnected |
| GET | `/execution/readiness` | `?recompute=true` | Morning readiness snapshot |
| POST | `/execution/run-now` | — | Manually trigger morning execution |

These paths match `frontend/src/app/core/services/broker.service.ts`.

### Broker credential model (BYOK)

Users bring their **own** API credentials — nothing shared:

- **Upstox**: the user registers an app at developer.upstox.com with redirect URI
  = `UPSTOX_REDIRECT_URI`, then enters their API key + secret. Standard OAuth.
- **Jainam (XTS Retail)**: the user requests XTS API activation from Jainam
  support and receives Interactive + Market Data key/secret pairs, entered in the
  app. Auth is a direct login (no OAuth), returning a session token valid for the
  trading day.

Credentials and tokens are encrypted (Fernet) in `credentials_store.enc` /
`token_store.enc`, keyed by the Firestore account id — never in Firestore.

## Scheduled jobs (IST, Mon–Fri)

| Time | Job |
|---|---|
| 08:00 | Flag expired broker tokens (`needsReauth`) |
| 08:05 | Compute readiness snapshot |
| 09:15 | Execute morning strategies (place orders) |
| 09:15 | Write market-open activity log |

Disable with `ENABLE_SCHEDULER=false`.

## Security notes

- **Broker tokens never touch Firestore or the frontend.** They are encrypted
  (Fernet) and stored in `token_store.enc`, keyed by the Firestore account id.
- Upstox API v2 issues **no refresh token**; access tokens expire ~03:30 IST
  daily, so users must reconnect each trading day. The 08:00 job flags lapsed
  tokens rather than renewing them.

## Known TODOs (Phase 2)

- `execution_service._build_orders_for()` is a stub — plug in real instrument
  selection / position sizing from each strategy definition.
- Add Firebase ID-token verification on `/execution/run-now` and other
  privileged endpoints (pair with the frontend `auth-token.interceptor`).
- Implement `services/jainam_service.py` once Jainam API details are confirmed.
