from __future__ import annotations

from datetime import datetime, timezone

import pytest
import pytest_asyncio

from app.database.connection import Database
from app.services.access_service import AccessService
from app.services.delivery_service import DeliveryService
from app.services.file_service import FileService, IncomingFile
from app.services.link_service import LinkService


@pytest_asyncio.fixture
async def database():
    db = Database("sqlite+aiosqlite:///:memory:")
    await db.create_tables()
    yield db
    await db.close()


@pytest.mark.asyncio
async def test_upload_reference_and_access_session(database):
    files = FileService(database)
    stored, created = await files.store_upload(
        IncomingFile(
            telegram_chat_id=100,
            telegram_message_id=5,
            telegram_file_id="telegram-file-id",
            telegram_file_unique_id="telegram-unique-id",
            file_name="example.txt",
            file_type="document",
            mime_type="text/plain",
            file_size=12,
        )
    )
    assert created is True
    assert await files.get_by_public_id(stored.public_id) is not None

    access = AccessService(database)
    first = await access.get_or_create_valid_session(77)
    second = await access.get_or_create_valid_session(77)
    assert first.id == second.id
    assert second.expires_at > datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.mark.asyncio
async def test_duplicate_source_message_is_not_stored_twice(database):
    files = FileService(database)
    incoming = IncomingFile(1, 2, "file", "unique", None, "document", None, None)
    first, created_first = await files.store_upload(incoming)
    second, created_second = await files.store_upload(incoming)
    assert created_first is True
    assert created_second is False
    assert first.id == second.id


@pytest.mark.asyncio
async def test_delivery_delete_time_is_configurable(database):
    files = FileService(database)
    stored, _ = await files.store_upload(IncomingFile(1, 3, "file2", "unique2", None, "video", None, 3))
    deliveries = DeliveryService(database, delete_after_minutes=1)
    delivery = await deliveries.record_delivery(55, stored.id, 55, 99)
    assert delivery.delete_at > delivery.sent_at
    assert delivery.status == "pending"


def test_deep_link_validation_rejects_arbitrary_values():
    assert LinkService.parse_file_id("file_AbCdEfGhIjKlMnOp") == "AbCdEfGhIjKlMnOp"
    assert LinkService.parse_file_id("file_short") is None
    assert LinkService.parse_file_id("file_../../secret") is None
    assert LinkService.parse_file_id("not-a-file-link") is None
