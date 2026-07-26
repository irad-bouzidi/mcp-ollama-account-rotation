from alembic.config import Config
from alembic import command


def run_migrations(database_url: str):
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", database_url.replace("+asyncpg", ""))
    command.upgrade(alembic_cfg, "head")
