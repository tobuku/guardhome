import aiosqlite
import os

DB_PATH = os.getenv("DB_PATH", "/data/guardhome.db")
_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


async def get_db():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        yield db


async def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with open(_SCHEMA_PATH) as f:
        schema = f.read()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(schema)
        # Migration: add deduplication index to dns_log if not present
        await db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_dns_log "
            "ON dns_log (child_id, domain, ts)"
        )
        await db.commit()
