import { useQuery } from '@tanstack/react-query';
import { statusApi } from '../api/client';
import ProviderCard from '../components/ProviderCard';

function Dashboard() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['status'],
    queryFn: statusApi.get,
  });

  if (isLoading) return <div className="text-gray-500">Loading...</div>;
  if (isError || !data) return <div className="text-red-500">Failed to load status</div>;

  return (
    <div>
      <div
        className={`rounded-lg p-4 mb-6 ${
          data.any_available
            ? 'bg-green-50 border border-green-200'
            : 'bg-red-50 border border-red-200'
        }`}
      >
        <p className={`font-medium ${data.any_available ? 'text-green-800' : 'text-red-800'}`}>
          {data.any_available
            ? 'All systems operational'
            : 'All accounts depleted! Add new accounts or switch providers.'}
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {data.providers.map((provider) => (
          <ProviderCard key={provider.id} provider={provider} />
        ))}
        {data.providers.length === 0 && (
          <p className="text-gray-500 col-span-full">No providers configured.</p>
        )}
      </div>
    </div>
  );
}

export default Dashboard;
