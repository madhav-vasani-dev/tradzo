export type BrokerName = 'upstox' | 'jainam';

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
  comingSoon?: boolean;
}

export const BROKER_REGISTRY: BrokerMeta[] = [
  {
    name: 'upstox',
    label: 'Upstox',
    description: 'Connect your Upstox account using your own Upstox API app. Supports F&O, equity, and index strategies.',
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
];
