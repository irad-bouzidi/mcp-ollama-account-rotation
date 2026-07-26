import asyncio

from alembic import command
from alembic.config import Config


async def run_migrations(database_url: str):
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", database_url.replace("+asyncpg", ""))
    await asyncio.to_thread(command.upgrade, alembic_cfg, "head")
