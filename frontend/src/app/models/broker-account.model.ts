export type BrokerName = 'upstox' | 'jainam' | 'delta' | 'kotak';

export interface BrokerAccount {
  id: string;                     // Firestore doc ID
  userId: string;
  broker: BrokerName;
  displayName: string;            // e.g. "Upstox — Madhav Vasani"
  brokerAccountId: string;        // Broker's own account ID (e.g. UPX123)
  isConnected: boolean;
  needsReauth?: boolean;          // true when the token lapsed and a reconnect is required
  connectedAt: any | null;        // Firestore Timestamp
  lastRefreshedAt: any | null;
  expiresAt: any | null;          // When the access token expires (display only — token itself is in backend)
  /** Kotak: the backend logs in automatically every trading day with the stored TOTP secret. */
  autoLogin?: boolean;
  lastLoginAt?: any | null;
  /** Last automatic-login / static-IP problem reported by the backend (null when healthy). */
  lastLoginError?: string | null;
  /** Kotak: the server IP Kotak saw at the last login — must be whitelisted on the Neo API dashboard. */
  kotakSeenIp?: string | null;
}

/** A single credential input the user must provide to connect a broker (BYOK). */
export interface BrokerCredentialField {
  key: string;            // request-body field name sent to the backend
  label: string;
  secret?: boolean;       // render as a password input
  required?: boolean;     // default true
  hint?: string;
}

/**
 * A URL the user must register in their broker developer app. `path` is the
 * backend path; the dialog prefixes it with the backend base URL and shows a
 * copy button.
 */
export interface BrokerSetupUrl {
  label: string;
  path: string;
  hint?: string;
}

/**
 * authType:
 *  - 'oauth'   → backend returns an auth_url; we redirect the browser to the broker.
 *  - 'session' → backend logs in synchronously with the keys; no redirect.
 */
export interface BrokerMeta {
  name: BrokerName;
  label: string;
  description: string;
  logoUrl: string;
  authType: 'oauth' | 'session';
  credentialFields: BrokerCredentialField[];
  setupUrls?: BrokerSetupUrl[];   // URLs to register in the broker's developer app
  helpText?: string;      // where to obtain the keys
  /** Ordered setup steps shown in the connect dialog (optional). */
  setupSteps?: string[];
  comingSoon?: boolean;
}

export const BROKER_REGISTRY: BrokerMeta[] = [
  {
    name: 'upstox',
    label: 'Upstox',
    description: 'Connect your Upstox account using your own Upstox API app. Supports options, futures, equity, and index strategies.',
    logoUrl: '',
    authType: 'oauth',
    credentialFields: [
      { key: 'apiKey', label: 'API Key', required: true },
      { key: 'apiSecret', label: 'API Secret', secret: true, required: true },
    ],
    setupUrls: [
      {
        label: 'Redirect URL',
        path: '/broker/upstox/callback',
        hint: 'Set this as the Redirect URI when creating your app on developer.upstox.com.',
      },
      {
        label: 'Postback URL',
        path: '/broker/upstox/postback',
        hint: 'Set this as the Postback URL in your Upstox app to receive order updates.',
      },
    ],
    helpText:
      'Create an app at developer.upstox.com, set the Redirect and Postback URLs below, ' +
      'then copy the app\'s API Key and Secret here.',
    comingSoon: false,
  },
  {
    name: 'jainam',
    label: 'Jainam',
    description: 'Connect your Jainam account via the Symphony XTS (Retail) API using your own API keys.',
    logoUrl: '',
    authType: 'session',
    credentialFields: [
      { key: 'interactiveApiKey', label: 'Interactive API Key', required: true },
      { key: 'interactiveApiSecret', label: 'Interactive API Secret', secret: true, required: true },
      { key: 'marketDataApiKey', label: 'Market Data API Key', required: false },
      { key: 'marketDataApiSecret', label: 'Market Data API Secret', secret: true, required: false },
    ],
    setupUrls: [
      {
        label: 'Redirect URL',
        path: '/broker/jainam/callback',
        hint: 'Use this as the Redirect URL in your XTS API app.',
      },
      {
        label: 'Postback URL',
        path: '/broker/jainam/postback',
        hint: 'Set this as the Postback (webhook) URL for your Interactive API app in the XTS dashboard.',
      },
    ],
    helpText:
      'Request XTS API activation from Jainam support for your client ID. They email you the ' +
      'Interactive and Market Data API key/secret pairs — enter them here.',
    comingSoon: false,
  },
  {
    name: 'kotak',
    label: 'Kotak Neo',
    description: 'Connect your Kotak Neo account via the Neo Trade API. Logs in automatically every trading day — supports Nifty options and MCX commodity options.',
    logoUrl: '',
    authType: 'session',
    credentialFields: [
      { key: 'accessToken', label: 'Trade API Access Token', secret: true, required: true,
        hint: 'Neo app/web → More → Trade API → your application → copy the token.' },
      { key: 'ucc', label: 'Client Code (UCC)', required: true, hint: 'Neo app → Profile, e.g. "AB123".' },
      { key: 'mobileNumber', label: 'Registered Mobile Number', required: true, hint: 'With country code, e.g. +919876543210.' },
      { key: 'mpin', label: 'MPIN', secret: true, required: true, hint: 'Your 6-digit Kotak Neo MPIN.' },
      { key: 'totpSecret', label: 'TOTP Secret Key', secret: true, required: true,
        hint: 'The text key shown under the QR code during TOTP registration (not the 6-digit code).' },
      { key: 'displayName', label: 'Display Name', required: false, hint: 'Optional label, e.g. the client\'s name.' },
    ],
    helpText:
      'Neo Trade API with automatic daily login: we generate the TOTP from your secret key, so you never ' +
      'have to log in by hand. Orders are only accepted from the static IP you whitelist.',
    setupSteps: [
      'Neo app or neo.kotaksecurities.com → More → Trade API → Create Application. Copy the access token.',
      'On the same API dashboard open "TOTP Registration", verify with mobile + OTP, and when the QR code ' +
        'appears ALSO copy the secret key text shown with it. Scan the QR in Google/Microsoft Authenticator and ' +
        'confirm the 6-digit code to finish registration.',
      'API dashboard → your application → Add IP: whitelist the Tradzo server IP (ask the Tradzo admin) as the ' +
        'primary IP. SEBI rules reject orders from any other IP.',
      'Enter the token, client code, mobile, MPIN and TOTP secret below.',
    ],
    comingSoon: false,
  },
  {
    name: 'delta',
    label: 'Delta Exchange',
    description: 'Connect your Delta Exchange account using your own API key and secret. Used for crypto options strategies.',
    logoUrl: '',
    authType: 'session',
    credentialFields: [
      { key: 'apiKey', label: 'API Key', required: true, hint: 'From Profile → API Management on delta.exchange' },
      { key: 'apiSecret', label: 'API Secret', secret: true, required: true },
      { key: 'displayName', label: 'Display Name', required: false, hint: 'Optional label, e.g. "My Delta Account"' },
    ],
    setupUrls: [
      {
        label: 'Postback URL',
        path: '/broker/delta/postback',
        hint: 'Optional: register this as a webhook in your Delta Exchange API settings for order updates.',
      },
    ],
    helpText:
      'Go to Profile → API Management on delta.exchange (or india.delta.exchange). ' +
      'Create a key with Read + Trading permissions, then paste the API Key and Secret here.',
    comingSoon: false,
  },
];
