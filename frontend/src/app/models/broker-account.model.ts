export type BrokerName = 'upstox' | 'jainam';

export interface BrokerAccount {
  id: string;                     // Firestore doc ID
  userId: string;
  broker: BrokerName;
  displayName: string;            // e.g. "Upstox — Madhav Vasani"
  brokerAccountId: string;        // Broker's own account ID (e.g. UPX123)
  isConnected: boolean;
  connectedAt: any | null;        // Firestore Timestamp
  lastRefreshedAt: any | null;
  expiresAt: any | null;          // When the access token expires (display only — token itself is in backend)
}

export interface BrokerMeta {
  name: BrokerName;
  label: string;
  description: string;
  logoUrl: string;            // Placeholder SVG/URL
  oauthSupported: boolean;
  comingSoon?: boolean;
}

export const BROKER_REGISTRY: BrokerMeta[] = [
  {
    name: 'upstox',
    label: 'Upstox',
    description: 'Connect your Upstox trading account via secure OAuth 2.0. Supports F&O, equity, and index strategies.',
    logoUrl: '',
    oauthSupported: true,
    comingSoon: false
  },
  {
    name: 'jainam',
    label: 'Jainam',
    description: 'Connect your Jainam Broking account. Full support coming soon.',
    logoUrl: '',
    oauthSupported: false,
    comingSoon: true
  }
];
