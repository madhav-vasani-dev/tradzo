# Tradzo — Phase 1 Implementation Plan (Final)

## Overview

**Tradzo** is an algorithmic trading platform built with **Angular 19 + Firebase (Firestore, Auth) + PrimeNG** on the frontend and a **Python backend** for execution logic. Phase 1 delivers four production-ready modules.

### Confirmed Decisions
| Decision | Answer |
|---|---|
| **Admin Role System** | One hard-coded superuser; superuser can grant/revoke `isAdmin` flag on any user |
| **Broker OAuth** | Upstox — confirmed OAuth 2.0. Jainam — TBD, will be added later |
| **Backend** | Python (FastAPI recommended) — runs separately from Firebase |
| **Strategy Source** | Admin creates strategies in-app → stored in Firestore; users view/deploy them |
| **Performance Data** | All key metrics stored statically per strategy in Phase 1; dynamic in Phase 2 |
| **Minimum Amount** | Part of the strategy data object in Firestore |
| **Token Storage** | Access + refresh tokens stored **only in the Python backend** (env/encrypted store). Never in Firestore or the Angular frontend. ✅ Confirmed |
| **Morning Execution** | Fully automatic — Python APScheduler job at 9:15 AM IST on weekdays |
| **Morning Readiness Panel** | Confirmed — built inside Activity Monitor as a dedicated pre-market panel |

---

## Architecture Overview

```
┌────────────────────────────────────────────────────────┐
│                  Angular 19 Frontend                   │
│         (Firebase Auth + Firestore reads)              │
└───────────────┬────────────────────────────────────────┘
                │ HTTP (REST calls for broker actions)
┌───────────────▼────────────────────────────────────────┐
│              Python FastAPI Backend                     │
│   - Upstox OAuth token exchange & refresh              │
│   - Morning order execution (APScheduler 9:15 AM IST)  │
│   - Writes activityLogs to Firestore via Admin SDK     │
│   - Reads userStrategies + brokerAccounts from Firestore│
└────────────────────────────────────────────────────────┘
                │ Firebase Admin SDK
┌───────────────▼────────────────────────────────────────┐
│                    Firebase / Firestore                 │
│   users | strategies | userStrategies                  │
│   brokerAccounts | activityLogs                        │
└────────────────────────────────────────────────────────┘
```

---

## Frontend File Structure

```
src/app/
├── core/
│   ├── guards/
│   │   ├── auth.guard.ts              (exists)
│   │   ├── admin.guard.ts             [NEW] — checks isAdmin or isSuperUser
│   │   └── superuser.guard.ts         [NEW] — only for superuser actions
│   ├── services/
│   │   ├── auth.service.ts            [NEW] — wraps Firebase Auth, exposes currentUser$
│   │   ├── strategy.service.ts        [NEW] — Firestore CRUD for strategies
│   │   ├── broker.service.ts          [NEW] — calls Python backend for OAuth + token ops
│   │   ├── user.service.ts            [NEW] — Firestore user management
│   │   └── activity.service.ts        [NEW] — Firestore activityLogs listener
│   └── interceptors/
│       └── auth-token.interceptor.ts  [NEW] — attaches Firebase ID token to backend requests
├── models/
│   ├── strategy.model.ts              [NEW]
│   ├── user.model.ts                  [NEW]
│   ├── broker-account.model.ts        [NEW]
│   └── activity-log.model.ts          [NEW]
├── pages/
│   ├── auth/                          (exists — minor update: superuser seeding note)
│   ├── dashboard/                     (exists — enhance with summary stat cards)
│   ├── sidebar/                       (exists — add all new nav items + admin section)
│   ├── strategies/
│   │   ├── strategies.component.*     [NEW] — strategy grid/browse page
│   │   └── strategy-detail/
│   │       └── strategy-detail.component.*  [NEW]
│   ├── broker-accounts/
│   │   └── broker-accounts.component.*      [NEW]
│   ├── profile/
│   │   └── profile.component.*              [NEW]
│   └── admin/
│       ├── users/
│       │   ├── users.component.*            [NEW]
│       │   └── user-detail/
│       │       └── user-detail.component.*  [NEW]
│       └── strategy-management/
│           ├── strategy-management.component.*   [NEW]
│           └── activity-monitor/
│               └── activity-monitor.component.*  [NEW]
├── shared/
│   ├── components/
│   │   ├── stat-card/             [NEW]
│   │   ├── strategy-card/         [NEW]
│   │   └── status-badge/          [NEW]
│   └── pipes/
│       └── inr-currency.pipe.ts   [NEW]
└── dialogs/
    ├── deploy-strategy-dialog/    [NEW]
    ├── connect-broker-dialog/     [NEW]
    └── manage-strategy-dialog/    [NEW] — add/edit strategy (admin)
```

---

## Firestore Data Models

### `users/{uid}`
```typescript
{
  uid: string,
  username: string,
  email: string,
  photoURL: string | null,
  isSuperUser: boolean,          // only one user, hardcoded by UID check or seeded manually
  isAdmin: boolean,              // superuser can toggle this on any user
  createdAt: Timestamp,
  deployedStrategyIds: string[], // quick lookup array
  brokerConnected: boolean,      // denormalized for quick header status check
}
```

### `strategies/{strategyId}`
```typescript
{
  id: string,
  name: string,
  description: string,           // rich text / long description
  category: 'Options' | 'Futures' | 'Equity' | 'Index',
  instrumentType: string,        // e.g. 'Nifty Options', 'BankNifty Futures'
  riskLevel: 'Low' | 'Medium' | 'High',
  isVisible: boolean,            // admin toggle — controls user visibility
  minimumAmount: number,         // e.g. 50000
  tags: string[],                // e.g. ['Intraday', 'Momentum']
  
  // --- Performance Data (Static in Phase 1, Dynamic in Phase 2) ---
  performance: {
    cagr: number,                     // % e.g. 42.5
    sharpeRatio: number,              // e.g. 1.8
    maxDrawdown: number,              // % e.g. 12.3
    winRate: number,                  // % e.g. 67.4
    totalTrades: number,
    avgTradeReturn: number,           // % average P&L per trade
    avgTradeDurationMinutes: number,
    profitFactor: number,             // gross profit / gross loss
    calmarRatio: number,              // CAGR / max drawdown
    expectancy: number,               // expected P&L per trade in ₹
    backtestStartDate: string,        // ISO date string
    backtestEndDate: string,
    monthlyReturns: {
      month: string,                  // 'Jan 2024'
      returnPct: number               // e.g. 4.2
    }[],
    yearlyReturns: {
      year: string,                   // '2024'
      returnPct: number
    }[],
    equityCurve: {                    // for line chart
      date: string,
      value: number                   // cumulative portfolio value
    }[]
  },
  
  createdAt: Timestamp,
  updatedAt: Timestamp,
  createdByUid: string,
}
```

### `userStrategies/{docId}` — Deployment Records
```typescript
{
  id: string,
  userId: string,
  strategyId: string,
  strategyName: string,          // denormalized for quick display
  brokerAccountId: string,
  brokerName: 'upstox' | 'jainam',
  deployedAmount: number,
  status: 'active' | 'paused' | 'stopped',
  deployedAt: Timestamp,
  lastTradedAt: Timestamp | null,
  pausedAt: Timestamp | null,
  stoppedAt: Timestamp | null,
  pausedByAdmin: boolean,        // true if admin force-paused
}
```

### `brokerAccounts/{docId}`
```typescript
{
  id: string,
  userId: string,
  broker: 'upstox' | 'jainam',
  accountId: string,             // broker's user/client ID
  displayName: string,           // e.g. "Upstox - John D."
  // ✅ CONFIRMED: accessToken and refreshToken are stored ONLY in the Python
  // backend's encrypted store. Firestore holds only metadata (expiry, status).
  isConnected: boolean,
  tokenExpiry: Timestamp,
  lastRefreshedAt: Timestamp,
  connectedAt: Timestamp,
}
// The Python backend is the single source of truth for all broker credentials.
```

### `activityLogs/{docId}`
```typescript
{
  id: string,
  type: 'order_placed' | 'order_failed' | 'order_modified' | 
        'strategy_triggered' | 'strategy_paused' | 'strategy_stopped' |
        'broker_connected' | 'broker_disconnected' | 'broker_token_refreshed' |
        'user_deployed' | 'user_paused' | 'admin_action',
  strategyId: string | null,
  strategyName: string | null,
  userId: string | null,
  userName: string | null,
  message: string,
  metadata: {                    // flexible, depends on type
    orderId?: string,
    orderType?: string,
    quantity?: number,
    price?: number,
    symbol?: string,
    errorCode?: string,
    errorMessage?: string,
  },
  severity: 'info' | 'warning' | 'error' | 'success',
  timestamp: Timestamp,
}
```

---

## Routing Structure

```
/auth                              → AuthComponent (public)
/auth/broker-callback              → BrokerCallbackComponent (public — Upstox OAuth return)

/dashboard                         → DashboardComponent (auth guarded)
/strategies                        → StrategiesComponent (auth guarded)
/strategies/:id                    → StrategyDetailComponent (auth guarded)
/broker-accounts                   → BrokerAccountsComponent (auth guarded)
/profile                           → ProfileComponent (auth guarded)

/admin                             → redirect → /admin/users
/admin/users                       → UsersComponent (admin guarded)
/admin/users/:id                   → UserDetailComponent (admin guarded)
/admin/strategies                  → StrategyManagementComponent (admin guarded)
/admin/activity                    → ActivityMonitorComponent (admin guarded)
```

---

## Module Specifications

---

### Module 1 — Strategies

#### `strategies.component` (Browse Page)
- **Header**: "Strategies" title + filter bar (Category chips, Risk Level chips, Search input)
- **Grid layout**: 3 columns desktop / 2 tablet / 1 mobile
- **`strategy-card` component** per strategy showing:
  - Strategy name + category chip
  - Risk badge (color-coded)
  - Key stats row: CAGR, Win Rate, Max Drawdown
  - Minimum amount tag
  - "View Details" button + "Deployed" badge if already active
- Queries Firestore: `strategies` where `isVisible == true`

#### `strategy-detail.component` (Detail Page)
**Sections (top to bottom):**

1. **Hero** — Name, category, risk badge, tags, short description
2. **Key Metrics Row** — 5 stat cards: CAGR · Sharpe Ratio · Max Drawdown · Win Rate · Profit Factor
3. **Secondary Metrics** — Calmar Ratio · Expectancy · Avg Trade Return · Avg Trade Duration · Total Trades
4. **Monthly Returns Chart** — PrimeNG Bar Chart, green/red bars per month
5. **Yearly Returns Table** — Year | Return % | vs Nifty (placeholder in Phase 1)
6. **Equity Curve** — PrimeNG Line Chart showing portfolio value over backtest period
7. **Backtest Period** — "Backtested from [date] to [date]"
8. **Deployment Panel** (bottom sticky or sidebar card):
   - If not deployed: "Deploy Strategy" button (opens `DeployStrategyDialog`)
   - If deployed: Status badge + Broker name + Amount + Pause / Stop buttons

#### `deploy-strategy-dialog`
PrimeNG stepper dialog (3 steps):
- **Step 1 — Select Broker**: Dropdown of user's connected broker accounts. If none connected → shows "Connect a Broker First" with link.
- **Step 2 — Set Amount**: Number input with min-amount shown below. Real-time validation.
- **Step 3 — Confirm**: Summary card (Strategy, Broker, Amount) + "Deploy" button.
- On confirm: writes `userStrategies` document, updates `users/{uid}.deployedStrategyIds` array.

---

### Module 2 — Broker Accounts

#### `broker-accounts.component`
- Two broker cards: **Upstox** and **Jainam** (Jainam shows "Coming Soon" until confirmed)
- **Upstox card** shows:
  - Connected state: Account ID, token expiry, last refreshed, "Disconnect" button
  - Disconnected state: "Connect Upstox" button → opens `ConnectBrokerDialog`
  - Near-expiry warning: if token expires within 1 hour → orange banner
- **Security note**: "Your credentials are never stored in our app"

#### `connect-broker-dialog`
- Upstox: "You will be redirected to Upstox to authorize access. Once approved, you'll be returned here automatically."
- On confirm → calls Python backend `/api/broker/upstox/auth-url` → redirects to Upstox OAuth page
- Upstox redirects back to `/auth/broker-callback?code=xxx`
- `broker-callback` component: sends `code` to Python backend `/api/broker/upstox/callback` → backend exchanges for tokens, stores securely, writes `brokerAccounts` doc to Firestore → redirect to `/broker-accounts` with success toast

#### `broker.service.ts`
```typescript
getAuthUrl(broker: string): Observable<string>          // GET /api/broker/:broker/auth-url
handleCallback(broker, code): Observable<void>          // POST /api/broker/:broker/callback
getBrokerAccounts(userId): Observable<BrokerAccount[]>  // Firestore query
disconnectBroker(accountId): Observable<void>           // DELETE /api/broker/account/:id
```

---

### Module 3 — Users Module (Admin)

#### Admin Role Logic
- **Superuser**: One account identified by a hardcoded UID in Firestore rules OR seeded at registration with `isSuperUser: true`. This person can never lose admin.
- **Admin**: Any user with `isAdmin: true` — set/unset by the superuser via the Users module.
- **`admin.guard.ts`**: Checks `isAdmin === true || isSuperUser === true` in the user document.
- **`superuser.guard.ts`**: Checks `isSuperUser === true` — used for the "Grant Admin" action.

#### `users.component` (Admin)
- PrimeNG DataTable: Avatar · Name · Email · Joined Date · Deployed Strategies Count · Broker Connected · Admin Badge · Actions
- Search by name/email
- "Make Admin" / "Remove Admin" toggle (superuser only — hidden for regular admins)
- Click row → `/admin/users/:id`

#### `user-detail.component` (Admin)
- **Top section**: User avatar, name, email, joined date, admin badge, broker connection status
- **Deployed Strategies table**: Strategy Name · Broker · Amount · Status · Deployed Date · Admin Actions (Force Pause / Force Stop)
- **Activity Timeline**: Recent activity logs filtered for this user (last 20 events)
- Force Pause/Stop: writes `status` and `pausedByAdmin: true` to `userStrategies` doc → Python backend respects this flag at execution time

---

### Module 4 — Strategy Management (Admin)

#### `strategy-management.component` (Admin)
- DataTable: Name · Category · Risk · Min Amount · Visible Toggle · Active Deployments Count · Actions
- **Visible Toggle**: PrimeNG InputSwitch inline — instantly writes `isVisible` to Firestore
- **"Add Strategy"** button → opens `manage-strategy-dialog` in create mode
- **Edit icon** → opens `manage-strategy-dialog` in edit mode (pre-filled)
- **Delete icon** → PrimeNG ConfirmDialog before deletion

#### `manage-strategy-dialog` (Add/Edit)
Multi-tab form dialog:
- **Tab 1 — Basic Info**: Name, description (textarea), category, risk level, tags, minimum amount, isVisible toggle
- **Tab 2 — Performance Metrics**: Number inputs for all `performance.*` fields (CAGR, Sharpe, Drawdown, Win Rate, etc.)
- **Tab 3 — Monthly Returns**: Dynamic table — add rows with (Month, Return %). Admin fills this from backtest data.
- **Tab 4 — Yearly Returns**: Same pattern as monthly.
- **Tab 5 — Equity Curve**: Paste JSON or manual date/value rows.
- On save: writes full strategy object to `strategies` Firestore collection.

#### `activity-monitor.component` (Admin)
- **Summary Row**: 4 stat cards — Orders Today · Failed Orders · Active Users · Strategies Running
- **Live Feed**: Real-time `onSnapshot` on `activityLogs` ordered by `timestamp desc`, limit 100
  - Each log entry: timestamp · severity icon · type chip · message · user name · strategy name
  - Color-coded left border: green=success, red=error, yellow=warning, blue=info
- **Filter Bar**: Date range picker · Severity filter · Type filter · Strategy filter · User filter
- **Export**: Download filtered logs as CSV

#### Morning Readiness Panel ✅ (Confirmed — part of Activity Monitor)

A dedicated panel visible **every weekday morning (from 8:00 AM to 9:30 AM IST)** inside the Activity Monitor page. Shows the admin a pre-market readiness checklist before the 9:15 AM execution fires.

**Panel Layout:**
- **Countdown timer** to 9:15 AM execution (large, prominent)
- **Readiness Summary**: `X / Y users ready` progress bar
- **User Readiness Table**: One row per user who has an active strategy deployment
  - Avatar + Name · Strategy Name · Broker · Token Status (✅ Valid / ⚠️ Expiring / ❌ Expired) · Last Refreshed
- **Strategies to Execute**: List of strategies with how many users will trade each
- **Estimated Orders**: Total order count across all users
- **Manual Trigger button** (superuser only): "Run Now" — calls Python backend to execute immediately (for testing)
- **Auto-hides after 9:30 AM**: Panel collapses once the execution window has passed

Data source: Python backend exposes `GET /api/execution/readiness` → returns pre-computed status for all active subscriptions. Frontend polls this every 60s between 8:00–9:30 AM IST.

---

## Python FastAPI Backend Structure

```
backend/
├── main.py                    # FastAPI app entry point
├── scheduler.py               # APScheduler setup — morning execution job
├── requirements.txt
├── .env                       # UPSTOX_CLIENT_ID, CLIENT_SECRET, FIREBASE_CREDS, etc.
├── routers/
│   ├── broker.py              # /api/broker/* — OAuth, token exchange
│   └── health.py              # /api/health
├── services/
│   ├── upstox_service.py      # Upstox API calls (OAuth + order placement)
│   ├── jainam_service.py      # Jainam (placeholder for now)
│   ├── firebase_service.py    # Firebase Admin SDK — Firestore read/write
│   └── execution_service.py   # Morning strategy execution orchestrator
├── models/
│   ├── broker_account.py
│   ├── user_strategy.py
│   └── activity_log.py
└── utils/
    ├── token_store.py         # Secure in-memory + encrypted Firestore token store
    └── logger.py              # Writes activity logs to Firestore
```

### Key Backend Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/broker/upstox/auth-url` | Returns Upstox OAuth redirect URL |
| `POST` | `/api/broker/upstox/callback` | Exchanges auth code for tokens, stores securely |
| `DELETE` | `/api/broker/account/{id}` | Disconnects broker, clears tokens |
| `GET` | `/api/health` | Health check |

### Scheduled Jobs (APScheduler)

| Job | Schedule | Action |
|---|---|---|
| `refresh_broker_tokens` | Daily 8:00 AM IST (Mon–Fri) | Loops all `brokerAccounts`, refreshes near-expiry tokens, updates `tokenExpiry` + `lastRefreshedAt` in Firestore |
| `compute_readiness_snapshot` | Daily 8:05 AM IST (Mon–Fri) | Builds readiness status per user, caches in memory for the `/api/execution/readiness` endpoint |
| `execute_morning_strategies` | Daily 9:15 AM IST (Mon–Fri) | For each active `userStrategies` where `status == active` and user has valid token, places orders via broker API, writes `activityLogs` |
| `log_market_open` | Daily 9:15 AM IST (Mon–Fri) | Writes "strategy_triggered" log to Firestore for admin visibility |

> [!CAUTION]
> Access tokens and refresh tokens must live **only** in the Python backend's environment/encrypted store. They should never pass through the Angular frontend or be stored in plain-text Firestore fields.

---

## Shared Design System

### Design Language
| Element | Value |
|---|---|
| **Font** | `Inter` from Google Fonts (weights 400, 500, 600, 700) |
| **Background** | `#080E1C` — deep space dark |
| **Surface/Card** | `rgba(255, 255, 255, 0.04)` with `1px solid rgba(255,255,255,0.07)` border |
| **Backdrop** | `blur(12px)` glassmorphism on cards/dialogs |
| **Primary** | Electric Cyan `#00C2E8` |
| **Accent** | Gold `#F4B942` — CTAs, highlights, active states |
| **Success** | `#22C55E` |
| **Warning** | `#F59E0B` |
| **Danger** | `#EF4444` |
| **Text Primary** | `#F0F4FF` |
| **Text Secondary** | `#8B95B0` |
| **Charts** | Custom dark palette — cyan/gold/green/red fills |

### Animations
- **Route transitions**: Fade + slide-up (150ms ease-out)
- **Stat cards**: Number count-up animation on first load
- **Strategy cards**: Hover lift (translateY -4px) + glow shadow
- **Activity feed**: New log entries slide in from top with fade

### Shared Components
| Component | Purpose |
|---|---|
| `stat-card` | Icon + label + value + optional trend arrow |
| `strategy-card` | Full strategy preview card for the browse grid |
| `status-badge` | `active` / `paused` / `stopped` / `pending` pill badges |
| `inr-currency.pipe` | Formats numbers as ₹1,23,456 (Indian format) |

---

## Sidebar Navigation Structure

```
MAIN
 📊  Dashboard
 🎯  Strategies
 🏦  Broker Accounts
 👤  Profile

ADMIN (visible only if isAdmin || isSuperUser)
 👥  Users
 ⚙️  Strategy Management
 📋  Activity Monitor
```

---

## Verification Plan

### Per Module Checklist
- `ng build` — zero TypeScript errors
- All routes navigate without 404
- Firestore security rules tested for user vs admin vs superuser
- Responsive layout verified at 375px, 768px, 1440px

### Functional Tests
| Test | Expected |
|---|---|
| Login with non-admin → access `/admin/users` | Redirected to `/dashboard` |
| Superuser grants admin to user | `isAdmin: true` written, user sees admin nav |
| Admin revokes admin from non-superuser | `isAdmin: false`, nav items hidden |
| Deploy strategy without broker connected | Error/prompt to connect broker first |
| Deploy below minimum amount | Validation error shown inline |
| Connect Upstox OAuth | Redirected to Upstox, returns to `/broker-accounts`, token stored |
| Admin toggles `isVisible` on strategy | Non-admin users immediately stop seeing it |
| Python job at 9:15 AM | Orders placed, `activityLogs` written, visible in Activity Monitor |
| Force-pause by admin | `userStrategies.status = paused`, Python skips user at next execution |
| Morning Readiness Panel at 8:05 AM | `/api/execution/readiness` returns correct user count + token statuses |
| Manual "Run Now" trigger (superuser) | Python executes immediately, logs appear in activity feed |
