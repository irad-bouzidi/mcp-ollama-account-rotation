# Step 6: React Frontend

## Goal

Build the React SPA management dashboard with provider CRUD, account CRUD, and system status overview.

---

## Pages & Components

### Layout

```
┌─────────────────────────────────────────────┐
│  [Logo]  AI Account Rotator                │
│  ┌──────┬──────────────────────────────────┐│
│  │ Nav  │  Content Area                    ││
│  │      │                                  ││
│  │ 📊   │  (router outlet)                 ││
│  │ Dashboard│                              ││
│  │      │                                  ││
│  │ 🔌   │                                  ││
│  │ Providers│                              ││
│  │      │                                  ││
│  │ 👤   │                                  ││
│  │ Accounts│                               ││
│  │      │                                  ││
│  └──────┴──────────────────────────────────┘│
└─────────────────────────────────────────────┘
```

### Pages

**1. Dashboard (`/`)**
- System status summary at the top
  - Total providers, total accounts, active accounts
  - Warning banner if any provider has all accounts depleted
- Provider cards grid (one per provider)
  - Provider name + color-coded status badge
  - Account counts: total / active / depleted
  - "Has available" indicator (green check / red X)
  - Current active account email (if any)
  - Link to Accounts page filtered by this provider

**2. Providers (`/providers`)**
- Table of providers with columns: name, display name, base URL, accounts count, actions
- "Add Provider" button → modal/form
- Each row: Edit button → modal, Delete button (with confirmation)
- Form fields: name (select from predefined or custom), display name, base URL

**3. Accounts (`/accounts`?provider_id=xxx)**
- Filter by provider (dropdown)
- Table of accounts: email, status badges (active/depleted), credits remaining, requests count, last error, actions
- "Add Account" button → modal/form
  - Provider (dropdown)
  - Email
  - API token (password field, visible toggle)
- Each row:
  - Toggle active/inactive button
  - Reset depletion button
  - Edit button
  - Delete button (with confirmation)

### Component Tree

```
App
├── Layout
│   ├── Sidebar (navigation)
│   └── Content (react-router <Outlet/>)
│
├── Dashboard
│   ├── StatusBanner (depletion alerts)
│   └── ProviderCard[] (status per provider)
│
├── Providers
│   ├── ProviderTable
│   ├── ProviderFormModal (create/edit)
│   └── ConfirmDialog (delete)
│
└── Accounts
    ├── ProviderFilter (dropdown)
    ├── AccountTable
    │   └── AccountRow
    │       └── StatusBadge (active/depleted)
    ├── AccountFormModal (create/edit)
    └── ConfirmDialog (delete)
```

---

## API Client

**`frontend/src/api/client.ts`**

```typescript
import axios from 'axios';

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
```

---

## Types

**`frontend/src/types/index.ts`**

```typescript
interface Provider {
  id: string;
  name: string;
  display_name: string | null;
  base_url: string | null;
  account_count: number;
  active_accounts: number;
  depleted_accounts: number;
  created_at: string;
}

interface Account {
  id: string;
  provider_id: string;
  email: string | null;
  is_active: boolean;
  is_depleted: boolean;
  credits_remaining: number | null;
  last_error: string | null;
  requests_count: number;
  rate_limit_reset: string | null;
  created_at: string;
}

interface ProviderStatus {
  id: string;
  name: string;
  display_name: string | null;
  total_accounts: number;
  active_accounts: number;
  depleted_accounts: number;
  has_available: boolean;
  current_active_account: Account | null;
}

interface SystemStatus {
  providers: ProviderStatus[];
  any_available: boolean;
  depleted_providers: string[];
}
```

---

## Styling

Use **Tailwind CSS** for styling. Keep it clean and functional.

Color scheme:
- Green: active / available
- Red: depleted / error
- Yellow: warning (some accounts depleted)
- Blue: primary actions

---

## Pages Detail

### Dashboard Page

Fetches `GET /api/status` on mount (via React Query `useQuery`).

Top banner:
- Green if `any_available === true` → "All systems operational"
- Red if `any_available === false` → "All accounts depleted! Add new accounts or switch providers."

Provider cards:
- Each card shows: name, total/active/depleted counts, current active account email
- Card border color: green (has available), yellow (some depleted but active remain), red (all depleted)

### Providers Page

Fetches `GET /api/providers` on mount.

Table:
| Name | Display Name | Base URL | Accounts | Actions |
|---|---|---|---|---|
| openrouter | OpenRouter | https://... | 3 active / 1 depleted | [Edit] [Delete] |

Clicking on a provider name navigates to Accounts page with that provider pre-selected.

### Accounts Page

Fetches `GET /api/accounts?provider_id=xxx` on mount, re-fetches when filter changes.

Table:
| Email | Status | Credits | Requests | Last Error | Actions |
|---|---|---|---|---|---|
| user@... | ● Active | 2.50 | 142 | — | [Toggle] [Reset] [Edit] [Delete] |
| user2@... | ● Depleted | 0.00 | 500 | Rate limited... | [Toggle] [Reset] [Edit] [Delete] |

Status badges:
- Active + Not depleted → green "Active"
- Active + Depleted → red "Depleted" (can be reset)
- Inactive → gray "Inactive"

---

## Verification

```bash
# Dev mode
cd frontend && npm run dev
# Open http://localhost:5173

# Production mode (via Docker)
docker compose up -d
curl http://localhost:5173/   # should return HTML
# Open http://localhost:5173 in browser
```

## Files to create

- `frontend/src/main.tsx`
- `frontend/src/App.tsx`
- `frontend/src/types/index.ts`
- `frontend/src/api/client.ts`
- `frontend/src/components/Layout.tsx`
- `frontend/src/components/StatusBadge.tsx`
- `frontend/src/components/ProviderCard.tsx`
- `frontend/src/components/AccountRow.tsx`
- `frontend/src/pages/Dashboard.tsx`
- `frontend/src/pages/Providers.tsx`
- `frontend/src/pages/Accounts.tsx`
