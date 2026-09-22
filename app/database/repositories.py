"""Database operations for stored Telegram file references."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import StoredFile


class StoredFileRepository:
    """Read and write source-message references."""

    async def get_by_source_message(self, session: AsyncSession, telegram_chat_id: int, telegram_message_id: int) -> StoredFile | None:
        result = await session.execute(select(StoredFile).where(StoredFile.telegram_chat_id == telegram_chat_id, StoredFile.telegram_message_id == telegram_message_id))
        return result.scalar_one_or_none()

    async def get_by_public_id(self, session: AsyncSession, public_id: str) -> StoredFile | None:
        result = await session.execute(select(StoredFile).where(StoredFile.public_id == public_id))
        return result.scalar_one_or_none()

    async def get_by_id(self, session: AsyncSession, stored_file_id: int) -> StoredFile | None:
        return await session.get(StoredFile, stored_file_id)

    async def create_or_get(self, session: AsyncSession, **values: object) -> tuple[StoredFile, bool]:
        """Store a source reference once; duplicate uploads return the existing row."""
        existing = await self.get_by_source_message(session, int(values["telegram_chat_id"]), int(values["telegram_message_id"]))
        if existing is not None:
            return existing, False

        stored_file = StoredFile(**values)
        session.add(stored_file)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            existing = await self.get_by_source_message(session, int(values["telegram_chat_id"]), int(values["telegram_message_id"]))
            if existing is None:
                raise
            return existing, False
        await session.refresh(stored_file)
        return stored_file, True
