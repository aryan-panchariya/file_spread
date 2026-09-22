"""Background cleanup of user-facing messages only."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy.exc import SQLAlchemyError

from app.services.delivery_service import DeliveryService

logger = logging.getLogger(__name__)


class DeletionService:
    def __init__(self, bot: Bot, delivery_service: DeliveryService, poll_seconds: int = 10) -> None:
        self._bot = bot
        self._delivery_service = delivery_service
        self._poll_seconds = poll_seconds
        self._stop_event = asyncio.Event()

    async def run(self) -> None:
        """Recover overdue deliveries and continue checking while polling runs."""
        while not self._stop_event.is_set():
            try:
                await self.process_due_deliveries()
            except SQLAlchemyError:
                logger.exception("Database error while checking pending message deletions")
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self._poll_seconds)
            except asyncio.TimeoutError:
                pass

    async def process_due_deliveries(self) -> None:
        for delivery in await self._delivery_service.pending_deliveries():
            try:
                await self._bot.delete_message(chat_id=delivery.sent_chat_id, message_id=delivery.sent_message_id)
            except TelegramAPIError as error:
                logger.warning("Could not delete delivery id=%s: %s", delivery.id, error)
                await self._delivery_service.mark_failed(delivery.id, str(error))
            else:
                await self._delivery_service.mark_deleted(delivery.id)
                logger.info("Deleted user-facing delivery id=%s", delivery.id)

    def stop(self) -> None:
        self._stop_event.set()
