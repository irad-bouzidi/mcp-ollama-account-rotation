import type { Account } from '../types';
import StatusBadge from './StatusBadge';

interface AccountRowProps {
  account: Account;
  onToggle: (id: string) => void;
  onReset: (id: string) => void;
  onEdit: (account: Account) => void;
  onDelete: (id: string) => void;
}

function AccountRow({ account, onToggle, onReset, onEdit, onDelete }: AccountRowProps) {
  return (
    <tr className="hover:bg-gray-50">
      <td className="px-4 py-3 text-sm text-gray-900">{account.email || '—'}</td>
      <td className="px-4 py-3"><StatusBadge active={account.is_active} depleted={account.is_depleted} /></td>
      <td className="px-4 py-3 text-sm text-gray-600">{account.credits_remaining ?? '—'}</td>
      <td className="px-4 py-3 text-sm text-gray-600">{account.requests_count}</td>
      <td className="px-4 py-3 text-sm text-gray-600 max-w-xs truncate">{account.last_error || '—'}</td>
      <td className="px-4 py-3">
        <div className="flex gap-1 flex-wrap">
          <button
            onClick={() => onToggle(account.id)}
            className="text-xs px-2 py-1 rounded bg-gray-100 hover:bg-gray-200 text-gray-700"
          >
            {account.is_active ? 'Deactivate' : 'Activate'}
          </button>
          {account.is_depleted && (
            <button
              onClick={() => onReset(account.id)}
              className="text-xs px-2 py-1 rounded bg-yellow-100 hover:bg-yellow-200 text-yellow-800"
            >
              Reset
            </button>
          )}
          <button
            onClick={() => onEdit(account)}
            className="text-xs px-2 py-1 rounded bg-blue-100 hover:bg-blue-200 text-blue-700"
          >
            Edit
          </button>
          <button
            onClick={() => onDelete(account.id)}
            className="text-xs px-2 py-1 rounded bg-red-100 hover:bg-red-200 text-red-700"
          >
            Delete
          </button>
        </div>
      </td>
    </tr>
  );
}

export default AccountRow;
