# Step 1: Project Scaffold & Docker Compose

## Goal

Create the full directory structure, Docker Compose orchestration, base Dockerfiles, dependency files, and environment config. After this step, `docker compose build` succeeds and containers start (even if the app doesn't do anything useful yet).

---

## Tasks

### 1.1 Create directory structure

```
backend/app/{models,schemas,routers,services/adapters}/
backend/alembic/versions/
frontend/src/{api,types,pages,components}
doc/
```

### 1.2 Root files

**`docker-compose.yml`**
- 3 services: `postgres`, `backend`, `frontend`
- Named volume `postgres_data`
- Environment variables from `.env` file
- Postgres health check
- Backend depends on postgres (condition: healthy)
- Frontend depends on backend, serves on port 80 (mapped to 5173)

**`.env.example`**
```ini
DB_PASSWORD=change_me_in_production
ENCRYPTION_KEY=change_me_too
```

### 1.3 Backend files

**`backend/Dockerfile`**
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**`backend/requirements.txt`**
```
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
sqlalchemy[asyncio]>=2.0.36
asyncpg>=0.30.0
alembic>=1.14.0
pydantic>=2.10.0
pydantic-settings>=2.6.0
fastmcp>=2.0.0
httpx>=0.28.0
cryptography>=44.0.0
```

**`backend/app/__init__.py`** — empty

**`backend/app/config.py`**
- `Settings(BaseSettings)` class reading from env:
  - `DATABASE_URL` (default: `postgresql+asyncpg://rotation_user:password@localhost/account_rotation`)
  - `ENCRYPTION_KEY`
  - `DEBUG` (default: `False`)
- Singleton `get_settings()` function

**`backend/app/main.py`**
- Minimal FastAPI app with:
  - Lifespan that initializes DB engine
  - Root health endpoint `GET /` → `{"status": "ok"}`
  - CORS middleware (allow frontend origin)

**`backend/app/database.py`**
- Async engine creation from `DATABASE_URL`
- `async_session` factory
- `get_db()` async generator dependency
- `Base = declarative_base()` from SQLAlchemy

### 1.4 Frontend files

**`frontend/Dockerfile`**
- Multi-stage build:
  1. Build stage: `node:22-alpine`, install deps, `npm run build`
  2. Serve stage: `nginx:alpine`, copy built assets + `nginx.conf`

**`frontend/nginx.conf`**
- Serves static files from `/usr/share/nginx/html`
- Proxies `/api/*` to backend at `http://backend:8000`

**`frontend/package.json`**
- Dependencies: `react`, `react-dom`, `react-router-dom`, `@tanstack/react-query`, `axios`
- Dev dependencies: `typescript`, `vite`, `@vitejs/plugin-react`, `tailwindcss`

**`frontend/vite.config.ts`**
- Proxy `/api` to `http://localhost:8000` in dev
- Set output dir to `dist`

**`frontend/index.html`** — standard Vite HTML shell

**`frontend/src/main.tsx`** — React root mount

**`frontend/src/App.tsx`** — Minimal app with router placeholder

**`frontend/tsconfig.json`** — Standard React TypeScript config

### 1.5 Verify

```bash
docker compose build
docker compose up -d
curl http://localhost:8000/          # → {"status": "ok"}
curl http://localhost:5173/          # → React app loads
docker compose down
```

## Files to create

- `docker-compose.yml` (root)
- `.env.example` (root)
- `backend/Dockerfile`
- `backend/requirements.txt`
- `backend/app/__init__.py`
- `backend/app/config.py`
- `backend/app/main.py`
- `backend/app/database.py`
- `backend/.env.example`
- `frontend/Dockerfile`
- `frontend/nginx.conf`
- `frontend/package.json`
- `frontend/tsconfig.json`
- `frontend/vite.config.ts`
- `frontend/index.html`
- `frontend/src/main.tsx`
- `frontend/src/App.tsx`
- `frontend/src/vite-env.d.ts`
