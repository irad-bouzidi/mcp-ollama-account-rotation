import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { providersApi } from '../api/client';
import type { Provider, ProviderCreate } from '../types';

const PROVIDER_NAMES = [
  'openai',
  'anthropic',
  'google',
  'openrouter',
  'ollama',
  'azure',
  'aws-bedrock',
  'custom',
];

function Providers() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [modal, setModal] = useState<{ open: boolean; provider?: Provider }>({ open: false });
  const [deleteId, setDeleteId] = useState<string | null>(null);

  const [form, setForm] = useState({ name: '', display_name: '', base_url: '' });
  const [customName, setCustomName] = useState(false);

  const { data: providers, isLoading } = useQuery({
    queryKey: ['providers'],
    queryFn: providersApi.list,
  });

  const createMutation = useMutation({
    mutationFn: (data: ProviderCreate) => providersApi.create(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['providers'] }),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<ProviderCreate> }) =>
      providersApi.update(id, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['providers'] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => providersApi.delete(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['providers'] }),
  });

  function openCreate() {
    setForm({ name: '', display_name: '', base_url: '' });
    setCustomName(false);
    setModal({ open: true });
  }

  function openEdit(provider: Provider) {
    setForm({
      name: provider.name,
      display_name: provider.display_name || '',
      base_url: provider.base_url || '',
    });
    setCustomName(!PROVIDER_NAMES.includes(provider.name));
    setModal({ open: true, provider });
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const payload: ProviderCreate = {
      name: form.name,
      display_name: form.display_name || null,
      base_url: form.base_url || null,
    };
    if (modal.provider) {
      updateMutation.mutate({ id: modal.provider.id, data: payload });
    } else {
      createMutation.mutate(payload);
    }
    setModal({ open: false });
  }

  if (isLoading) return <div className="text-gray-500">Loading...</div>;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold text-gray-900">Providers</h2>
        <button
          onClick={openCreate}
          className="px-3 py-1.5 bg-blue-600 text-white rounded-md text-sm hover:bg-blue-700"
        >
          Add Provider
        </button>
      </div>

      <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Name</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Display Name</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Base URL</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Accounts</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {providers?.map((p) => (
              <tr key={p.id} className="hover:bg-gray-50">
                <td className="px-4 py-3">
                  <button
                    onClick={() => navigate(`/accounts?provider_id=${p.id}`)}
                    className="text-sm font-medium text-blue-600 hover:text-blue-800"
                  >
                    {p.name}
                  </button>
                </td>
                <td className="px-4 py-3 text-sm text-gray-600">{p.display_name || '—'}</td>
                <td className="px-4 py-3 text-sm text-gray-600 max-w-xs truncate">{p.base_url || '—'}</td>
                <td className="px-4 py-3 text-sm text-gray-600">
                  {p.active_accounts} active / {p.depleted_accounts} depleted
                </td>
                <td className="px-4 py-3">
                  <div className="flex gap-1">
                    <button
                      onClick={() => openEdit(p)}
                      className="text-xs px-2 py-1 rounded bg-blue-100 hover:bg-blue-200 text-blue-700"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => setDeleteId(p.id)}
                      className="text-xs px-2 py-1 rounded bg-red-100 hover:bg-red-200 text-red-700"
                    >
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {(!providers || providers.length === 0) && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-gray-500">
                  No providers found.
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
              {modal.provider ? 'Edit Provider' : 'Add Provider'}
            </h3>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
                {customName ? (
                  <input
                    type="text"
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
                    required
                  />
                ) : (
                  <select
                    value={form.name}
                    onChange={(e) => {
                      if (e.target.value === '__custom__') {
                        setCustomName(true);
                        setForm({ ...form, name: '' });
                      } else {
                        setForm({ ...form, name: e.target.value });
                      }
                    }}
                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
                    required
                  >
                    <option value="">Select a provider...</option>
                    {PROVIDER_NAMES.map((n) => (
                      <option key={n} value={n}>
                        {n}
                      </option>
                    ))}
                    <option value="__custom__">Custom...</option>
                  </select>
                )}
                {customName && (
                  <button
                    type="button"
                    onClick={() => {
                      setCustomName(false);
                      setForm({ ...form, name: '' });
                    }}
                    className="text-xs text-blue-600 mt-1"
                  >
                    Back to predefined
                  </button>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Display Name</label>
                <input
                  type="text"
                  value={form.display_name}
                  onChange={(e) => setForm({ ...form, display_name: e.target.value })}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Base URL</label>
                <input
                  type="text"
                  value={form.base_url}
                  onChange={(e) => setForm({ ...form, base_url: e.target.value })}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
                  placeholder="https://api.openai.com/v1"
                />
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
                  {modal.provider ? 'Update' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {deleteId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-lg p-6 w-full max-w-sm">
            <h3 className="text-lg font-semibold mb-2">Delete Provider</h3>
            <p className="text-sm text-gray-600 mb-4">
              Are you sure you want to delete this provider? This action cannot be undone.
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

export default Providers;
