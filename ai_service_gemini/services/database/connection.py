import asyncpg

from config import settings

_pool: asyncpg.Pool | None = None


async def connect_db() -> None:
    global _pool
    try:
        _pool = await asyncpg.create_pool(
            dsn=settings.database_url,
            min_size=2,
            max_size=10,
            command_timeout=30,
        )
        print("[DB] Connection pool created.")
    except Exception as e:
        print(f"[DB] WARNING — could not connect to database: {e}")
        print("[DB] Service will start in degraded mode (no DB). Fix DATABASE_URL in .env")
        _pool = None


async def disconnect_db() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool | None:
    return _pool
