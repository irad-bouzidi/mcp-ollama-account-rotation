# Step 2: Database Layer

## Goal

Define SQLAlchemy ORM models for the three database tables, configure Alembic for migrations, and create the initial migration. After this step, `alembic upgrade head` creates all tables.

---

## Tasks

### 2.1 SQLAlchemy Models

**`backend/app/models/__init__.py`** — import all models

**`backend/app/models/base.py`** (optional — or put in `database.py`)
- `Base` declarative base
- `TimestampMixin` with `created_at` / `updated_at` auto-updating columns

**`backend/app/models/provider.py`**
```python
class Provider(Base, TimestampMixin):
    __tablename__ = "providers"

    id: Mapped[UUID] = mapped_column(UUID, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=True)
    base_url: Mapped[str] = mapped_column(String(255), nullable=True)
    accounts: Mapped[list["Account"]] = relationship(back_populates="provider", cascade="all, delete-orphan")
```

**`backend/app/models/account.py`**
```python
class Account(Base, TimestampMixin):
    __tablename__ = "accounts"

    id: Mapped[UUID] = mapped_column(UUID, primary_key=True, default=uuid4)
    provider_id: Mapped[UUID] = mapped_column(ForeignKey("providers.id", ondelete="CASCADE"), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=True)
    api_token: Mapped[str] = mapped_column(String(512), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_depleted: Mapped[bool] = mapped_column(Boolean, default=False)
    credits_remaining: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    requests_count: Mapped[int] = mapped_column(Integer, default=0)
    rate_limit_reset: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    provider: Mapped["Provider"] = relationship(back_populates="accounts")
    usage_logs: Mapped[list["UsageLog"]] = relationship(back_populates="account", cascade="all, delete-orphan")
```

**`backend/app/models/usage_log.py`**
```python
class UsageLog(Base, TimestampMixin):
    __tablename__ = "usage_logs"

    id: Mapped[UUID] = mapped_column(UUID, primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    provider_id: Mapped[UUID] = mapped_column(ForeignKey("providers.id", ondelete="CASCADE"), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    request_type: Mapped[str] = mapped_column(String(50), default="chat")
    tokens_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    account: Mapped["Account"] = relationship(back_populates="usage_logs")
    provider: Mapped["Provider"] = relationship()
```

### 2.2 Alembic Configuration

**`backend/alembic/env.py`**
- Import `Base` from `app.models`
- Set `target_metadata = Base.metadata`
- Read `DATABASE_URL` from config/settings
- Configure async Alembic runner with `run_async()`

**`backend/alembic.ini`** (at `backend/` level)
- Point `script_location` to `alembic`
- Point to `app/alembic/env.py`

**`backend/app/alembic.py`** — helper module:
```python
from alembic.config import Config
from alembic import command

def run_migrations(database_url: str):
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", database_url.replace("+asyncpg", ""))
    command.upgrade(alembic_cfg, "head")
```

### 2.3 Initial Migration

Generate and review the initial migration:
```bash
cd backend
alembic revision --autogenerate -m "initial_schema"
alembic upgrade head
```

### 2.4 Seed Script (optional, for dev)

**`backend/app/seed.py`**
- Insert default providers: `ollama`, `openrouter`, `nvidia-nim`
- Run on first startup if providers table is empty

### 2.5 Update main.py

- Add lifespan that runs migrations on startup (via `run_migrations`)
- Add startup seed logic

## Verification

```bash
docker compose up -d postgres
docker compose run --rm backend alembic upgrade head
docker compose run --rm backend python -c "
from app.database import async_session
from app.models.provider import Provider
import asyncio
async def test():
    async with async_session() as s:
        print(await s.execute(select(Provider)).scalars().all())
asyncio.run(test())
"
```

## Files to create

- `backend/app/models/__init__.py`
- `backend/app/models/provider.py`
- `backend/app/models/account.py`
- `backend/app/models/usage_log.py`
- `backend/alembic.ini`
- `backend/alembic/env.py`
- `backend/alembic/script.py.mako`
- `backend/app/seed.py`
