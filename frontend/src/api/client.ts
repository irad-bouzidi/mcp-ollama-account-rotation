import axios from 'axios';
import type { Provider, ProviderCreate, ProviderUpdate, Account, AccountCreate, AccountUpdate, SystemStatus } from '../types';

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
});

export const providersApi = {
  list: () => api.get<Provider[]>('/providers').then(r => r.data),
  get: (id: string) => api.get<Provider>(`/providers/${id}`).then(r => r.data),
  create: (data: ProviderCreate) => api.post<Provider>('/providers', data).then(r => r.data),
  update: (id: string, data: ProviderUpdate) => api.put<Provider>(`/providers/${id}`, data).then(r => r.data),
  delete: (id: string) => api.delete(`/providers/${id}`),
};

export const accountsApi = {
  list: (providerId?: string) =>
    api.get<Account[]>('/accounts', { params: { provider_id: providerId } }).then(r => r.data),
  get: (id: string) => api.get<Account>(`/accounts/${id}`).then(r => r.data),
  create: (data: AccountCreate) => api.post<Account>('/accounts', data).then(r => r.data),
  update: (id: string, data: AccountUpdate) => api.put<Account>(`/accounts/${id}`, data).then(r => r.data),
  delete: (id: string) => api.delete(`/accounts/${id}`),
  toggle: (id: string) => api.post<Account>(`/accounts/${id}/toggle`).then(r => r.data),
  reset: (id: string) => api.post<Account>(`/accounts/${id}/reset`).then(r => r.data),
};

export const statusApi = {
  get: () => api.get<SystemStatus>('/status').then(r => r.data),
};
