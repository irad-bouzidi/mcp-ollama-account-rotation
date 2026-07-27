import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { accountsApi, providersApi } from '../api/client';
import type { Account, AccountCreate } from '../types';
import AccountRow from '../components/AccountRow';

function Accounts() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const providerId = searchParams.get('provider_id') || '';

  const [modal, setModal] = useState<{ open: boolean; account?: Account }>({ open: false });
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [showToken, setShowToken] = useState(false);

  const [form, setForm] = useState({ provider_id: '', email: '', api_token: '' });

  const { data: providers } = useQuery({
    queryKey: ['providers'],
    queryFn: providersApi.list,
  });

  const { data: accounts, isLoading } = useQuery({
    queryKey: ['accounts', providerId],
    queryFn: () => accountsApi.list(providerId || undefined),
  });

  const createMutation = useMutation({
    mutationFn: (data: AccountCreate) => accountsApi.create(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['accounts'] }),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<AccountCreate> }) =>
      accountsApi.update(id, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['accounts'] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => accountsApi.delete(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['accounts'] }),
  });

  const toggleMutation = useMutation({
    mutationFn: (id: string) => accountsApi.toggle(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['accounts'] }),
  });

  const resetMutation = useMutation({
    mutationFn: (id: string) => accountsApi.reset(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['accounts'] }),
  });

  function openCreate() {
    setForm({ provider_id: providerId, email: '', api_token: '' });
    setModal({ open: true });
  }

  function openEdit(account: Account) {
    setForm({
      provider_id: account.provider_id,
      email: account.email || '',
      api_token: '',
    });
    setModal({ open: true, account });
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const payload: AccountCreate = {
      provider_id: form.provider_id,
      email: form.email,
    };
    if (form.api_token) payload.api_token = form.api_token;

    if (modal.account) {
      updateMutation.mutate({ id: modal.account.id, data: payload });
    } else {
      createMutation.mutate(payload);
    }
    setModal({ open: false });
  }

  if (isLoading) return <div className="text-gray-500">Loading...</div>;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold text-gray-900">Accounts</h2>
        <div className="flex items-center gap-2">
          <select
            value={providerId}
            onChange={(e) => {
              const params = new URLSearchParams();
              if (e.target.value) params.set('provider_id', e.target.value);
              setSearchParams(params);
            }}
            className="border border-gray-300 rounded-md px-3 py-1.5 text-sm"
          >
            <option value="">All Providers</option>
            {providers?.map((p) => (
              <option key={p.id} value={p.id}>
                {p.display_name || p.name}
              </option>
            ))}
          </select>
          <button
            onClick={openCreate}
            className="px-3 py-1.5 bg-blue-600 text-white rounded-md text-sm hover:bg-blue-700"
          >
            Add Account
          </button>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Email</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Status</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Credits</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Requests</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Last Error</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {accounts?.map((a) => (
              <AccountRow
                key={a.id}
                account={a}
                onToggle={(id) => toggleMutation.mutate(id)}
                onReset={(id) => resetMutation.mutate(id)}
                onEdit={openEdit}
                onDelete={setDeleteId}
              />
            ))}
            {(!accounts || accounts.length === 0) && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-500">
                  No accounts found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {modal.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h3 className="text-lg font-semibold mb-4">
              {modal.account ? 'Edit Account' : 'Add Account'}
            </h3>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Provider</label>
                <select
                  value={form.provider_id}
                  onChange={(e) => setForm({ ...form, provider_id: e.target.value })}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
                  required
                >
                  <option value="">Select a provider...</option>
                  {providers?.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.display_name || p.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                <input
                  type="email"
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">API Token</label>
                <div className="relative">
                  <input
                    type={showToken ? 'text' : 'password'}
                    value={form.api_token}
                    onChange={(e) => setForm({ ...form, api_token: e.target.value })}
                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm pr-10"
                    required={!modal.account}
                  />
                  <button
                    type="button"
                    onClick={() => setShowToken(!showToken)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-gray-500 hover:text-gray-700"
                  >
                    {showToken ? 'Hide' : 'Show'}
                  </button>
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setModal({ open: false })}
                  className="px-3 py-1.5 text-sm border border-gray-300 rounded-md hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700"
                >
                  {modal.account ? 'Update' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {deleteId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-lg p-6 w-full max-w-sm">
            <h3 className="text-lg font-semibold mb-2">Delete Account</h3>
            <p className="text-sm text-gray-600 mb-4">
              Are you sure you want to delete this account? This action cannot be undone.
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setDeleteId(null)}
                className="px-3 py-1.5 text-sm border border-gray-300 rounded-md hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  deleteMutation.mutate(deleteId);
                  setDeleteId(null);
                }}
                className="px-3 py-1.5 text-sm bg-red-600 text-white rounded-md hover:bg-red-700"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Accounts;
