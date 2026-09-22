"""Optional required-channel membership checks."""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

logger = logging.getLogger(__name__)


class SubscriptionService:
    def __init__(self, bot: Bot, enabled: bool, channel_id: str | None, channel_username: str | None) -> None:
        if enabled and (not channel_id or not channel_username):
            raise ValueError("FORCE_SUBSCRIPTION_ENABLED requires REQUIRED_CHANNEL_ID and REQUIRED_CHANNEL_USERNAME.")
        self._bot = bot
        self.enabled = enabled
        self.channel_id = channel_id
        self.channel_username = channel_username.lstrip("@") if channel_username else None

    async def is_subscribed(self, user_telegram_id: int) -> bool:
        if not self.enabled:
            return True
        try:
            member = await self._bot.get_chat_member(chat_id=self.channel_id, user_id=user_telegram_id)
        except TelegramAPIError:
            logger.exception("Could not check channel membership for user id=%s", user_telegram_id)
            raise
        return member.status in {"creator", "administrator", "member"} or (
            member.status == "restricted" and bool(member.is_member)
        )

    def join_url(self) -> str:
        if not self.channel_username:
            raise ValueError("Required channel username is not configured.")
        return f"https://t.me/{self.channel_username}"
