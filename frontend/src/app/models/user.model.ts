export interface TradzoUser {
  uid: string;
  username: string;
  email: string;
  photoURL: string | null;
  isSuperUser: boolean;
  isAdmin: boolean;
  createdAt: any;
  updatedAt?: any;
  deployedStrategyIds?: string[];
  brokerConnected?: boolean;
  paperTrading?: boolean;
}

