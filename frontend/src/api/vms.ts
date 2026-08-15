import { apiGet } from './client';

export type VmsSession = {
  appId: string;
  apiKey: string;
  apiSecret: string;
  sceneId: string;
  avatarId: string;
  vcn: string;
  serverUrl: string;
  idleSec: number;
};

export const fetchVmsSession = () => apiGet<VmsSession>('/api/vms/session', { timeoutMs: 90_000 });
