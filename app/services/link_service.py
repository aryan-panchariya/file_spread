"""Telegram deep-link creation and validation."""

from __future__ import annotations

import re

from app.database.models import StoredFile

_PUBLIC_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{12,40}$")
_START_PREFIX = "file_"


class LinkService:
    """Build links that Telegram turns into /start payloads."""

    def __init__(self, bot_username: str) -> None:
        if not bot_username:
            raise ValueError("Telegram did not provide a bot username, so deep links cannot be created.")
        self._bot_username = bot_username.lstrip("@")

    def build_file_link(self, stored_file: StoredFile) -> str:
        return f"https://t.me/{self._bot_username}?start={_START_PREFIX}{stored_file.public_id}"

    @staticmethod
    def parse_file_id(start_argument: str | None) -> str | None:
        """Return only a well-formed generated public ID, never user-provided arbitrary data."""
        if not start_argument or not start_argument.startswith(_START_PREFIX):
            return None
        public_id = start_argument.removeprefix(_START_PREFIX)
        return public_id if _PUBLIC_ID_PATTERN.fullmatch(public_id) else None
