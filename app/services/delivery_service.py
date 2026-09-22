"""Delivery persistence for copied user-facing messages."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.database.connection import Database
from app.database.models import Delivery


class DeliveryService:
    def __init__(self, database: Database, delete_after_minutes: int) -> None:
        self._database = database
        self._delete_after = timedelta(minutes=delete_after_minutes)

    async def record_delivery(self, user_telegram_id: int, stored_file_id: int, sent_chat_id: int, sent_message_id: int) -> Delivery:
        sent_at = datetime.now(timezone.utc)
        delivery = Delivery(
            user_telegram_id=user_telegram_id,
            stored_file_id=stored_file_id,
            sent_chat_id=sent_chat_id,
            sent_message_id=sent_message_id,
            sent_at=sent_at,
            delete_at=sent_at + self._delete_after,
        )
        async with self._database.session_factory() as session:
            session.add(delivery)
            await session.commit()
            await session.refresh(delivery)
            return delivery

    async def pending_deliveries(self) -> list[Delivery]:
        now = datetime.now(timezone.utc)
        async with self._database.session_factory() as session:
            result = await session.execute(select(Delivery).where(Delivery.status == "pending", Delivery.delete_at <= now))
            return list(result.scalars().all())

    async def mark_deleted(self, delivery_id: int) -> None:
        async with self._database.session_factory() as session:
            delivery = await session.get(Delivery, delivery_id)
            if delivery:
                delivery.status = "deleted"
                delivery.deleted_at = datetime.now(timezone.utc)
                await session.commit()

    async def mark_failed(self, delivery_id: int, error_message: str) -> None:
        async with self._database.session_factory() as session:
            delivery = await session.get(Delivery, delivery_id)
            if delivery:
                delivery.status = "failed"
                delivery.error_message = error_message[:512]
                await session.commit()
