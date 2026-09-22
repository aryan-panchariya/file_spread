"""Minimal Telegram-user activity tracking."""

from __future__ import annotations

from datetime import datetime, timezone

from app.database.connection import Database
from app.database.models import User


class UserService:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def record_seen(self, telegram_id: int, username: str | None) -> User:
        now = datetime.now(timezone.utc)
        async with self._database.session_factory() as session:
            user = await session.get(User, telegram_id)
            if user is None:
                user = User(telegram_id=telegram_id, username=username, first_seen=now, last_seen=now)
                session.add(user)
            else:
                user.username = username
                user.last_seen = now
                user.status = "active"
            await session.commit()
            await session.refresh(user)
            return user
