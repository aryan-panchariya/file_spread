"""Async SQLAlchemy connection lifecycle."""

from __future__ import annotations

from pathlib import Path
import secrets

from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.database.models import Base


class Database:
    """Own the async database engine and sessions for this application process."""

    def __init__(self, database_url: str) -> None:
        self._create_sqlite_parent_directory(database_url)
        self.engine: AsyncEngine = create_async_engine(database_url)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

    @staticmethod
    def _create_sqlite_parent_directory(database_url: str) -> None:
        """Create the local SQLite folder, while leaving future PostgreSQL URLs untouched."""
        url = make_url(database_url)
        if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
            return
        Path(url.database).parent.mkdir(parents=True, exist_ok=True)

    async def create_tables(self) -> None:
        """Create tables and apply the small local Phase 3 SQLite migration if needed."""
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            if self.engine.url.get_backend_name() == "sqlite":
                await self._migrate_sqlite_public_ids(connection)

    @staticmethod
    async def _migrate_sqlite_public_ids(connection: object) -> None:
        """Give existing Phase 2 uploads a public ID without discarding local data."""
        # Phase 2 users may already have data/bot.db. SQLite create_all does not add columns.
        column_names = await connection.run_sync(lambda sync_connection: {column["name"] for column in inspect(sync_connection).get_columns("stored_files")})
        if "public_id" not in column_names:
            await connection.execute(text("ALTER TABLE stored_files ADD COLUMN public_id VARCHAR(40)"))

        rows = (await connection.execute(text("SELECT id FROM stored_files WHERE public_id IS NULL"))).all()
        for (row_id,) in rows:
            await connection.execute(
                text("UPDATE stored_files SET public_id = :public_id WHERE id = :row_id"),
                {"public_id": secrets.token_urlsafe(12), "row_id": row_id},
            )
        await connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_stored_files_public_id ON stored_files (public_id)"))

    async def close(self) -> None:
        """Release local database resources during bot shutdown."""
        await self.engine.dispose()
