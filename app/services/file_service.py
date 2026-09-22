"""Service layer for storing Telegram file message references."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import secrets
from sqlalchemy.exc import IntegrityError

from app.database.connection import Database
from app.database.models import StoredFile
from app.database.repositories import StoredFileRepository


@dataclass(frozen=True)
class IncomingFile:
    """Metadata extracted from a Telegram upload without downloading its contents."""

    telegram_chat_id: int
    telegram_message_id: int
    telegram_file_id: str
    telegram_file_unique_id: str
    file_name: str | None
    file_type: str
    mime_type: str | None
    file_size: int | None


class FileService:
    def __init__(self, database: Database) -> None:
        self._database = database
        self._repository = StoredFileRepository()

    async def store_upload(self, incoming_file: IncomingFile) -> tuple[StoredFile, bool]:
        async with self._database.session_factory() as session:
            values = asdict(incoming_file)
            for _ in range(3):
                try:
                    return await self._repository.create_or_get(
                        session, public_id=secrets.token_urlsafe(12), **values
                    )
                except IntegrityError:
                    # A public ID collision is exceptionally unlikely; retry without changing the source reference.
                    continue
            raise RuntimeError("Could not generate a unique public file ID after three attempts.")

    async def get_by_public_id(self, public_id: str) -> StoredFile | None:
        async with self._database.session_factory() as session:
            return await self._repository.get_by_public_id(session, public_id)

    async def get_by_id(self, stored_file_id: int) -> StoredFile | None:
        async with self._database.session_factory() as session:
            return await self._repository.get_by_id(session, stored_file_id)
