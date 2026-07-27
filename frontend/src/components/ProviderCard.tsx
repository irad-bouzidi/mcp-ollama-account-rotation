import { Link } from 'react-router-dom';
import type { ProviderStatus } from '../types';

interface ProviderCardProps {
  provider: ProviderStatus;
}

function borderColor(provider: ProviderStatus): string {
  if (!provider.has_available) return 'border-red-400';
  if (provider.depleted_accounts > 0) return 'border-yellow-400';
  return 'border-green-400';
}

function ProviderCard({ provider }: ProviderCardProps) {
  return (
    <div className={`bg-white rounded-lg shadow-sm border-l-4 ${borderColor(provider)} p-4`}>
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-semibold text-gray-900">{provider.display_name || provider.name}</h3>
        {provider.has_available ? (
          <span className="text-green-600 text-sm font-medium">✓ Available</span>
        ) : (
          <span className="text-red-600 text-sm font-medium">✗ Depleted</span>
        )}
      </div>
      <div className="space-y-1 text-sm text-gray-600">
        <p>Total: {provider.total_accounts} | Active: {provider.active_accounts} | Depleted: {provider.depleted_accounts}</p>
        {provider.current_active_account && (
          <p className="text-gray-500">Active: {provider.current_active_account.email || 'N/A'}</p>
        )}
      </div>
      <Link
        to={`/accounts?provider_id=${provider.id}`}
        className="mt-2 inline-block text-sm text-blue-600 hover:text-blue-800"
      >
        View accounts →
      </Link>
    </div>
  );
}

export default ProviderCard;
