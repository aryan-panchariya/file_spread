"""24-hour access-session persistence."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import secrets

from sqlalchemy import delete, select

from app.database.connection import Database
from app.database.models import AccessSession


class AccessService:
    """Find, create, and revoke 24-hour access sessions."""

    def __init__(self, database: Database, lifetime_hours: int = 24) -> None:
        self._database = database
        self._lifetime = timedelta(hours=lifetime_hours)

    async def get_valid_session(
        self,
        user_telegram_id: int,
    ) -> AccessSession | None:
        now = datetime.now(timezone.utc)

        async with self._database.session_factory() as session:
            result = await session.execute(
                select(AccessSession)
                .where(
                    AccessSession.user_telegram_id == user_telegram_id,
                    AccessSession.expires_at > now,
                )
                .order_by(AccessSession.expires_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()

    async def create_session(
        self,
        user_telegram_id: int,
    ) -> AccessSession:
        now = datetime.now(timezone.utc)

        access_session = AccessSession(
            user_telegram_id=user_telegram_id,
            session_token=secrets.token_urlsafe(48),
            created_at=now,
            expires_at=now + self._lifetime,
        )

        async with self._database.session_factory() as session:
            session.add(access_session)
            await session.commit()
            await session.refresh(access_session)
            return access_session

    async def get_or_create_valid_session(
        self,
        user_telegram_id: int,
    ) -> AccessSession:
        existing = await self.get_valid_session(user_telegram_id)

        if existing is not None:
            return existing

        return await self.create_session(user_telegram_id)

    async def revoke_user_sessions(
        self,
        user_telegram_id: int,
    ) -> int:
        """Delete all access sessions for a user."""

        async with self._database.session_factory() as session:
            result = await session.execute(
                delete(AccessSession).where(
                    AccessSession.user_telegram_id == user_telegram_id
                )
            )

            await session.commit()

            return result.rowcount or 0