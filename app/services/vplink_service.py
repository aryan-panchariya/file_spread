"""Small async client for the VPLINK shortening API."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class VplinkError(Exception):
    """A safe, user-independent error from VPLINK."""


class VplinkService:
    """Generate VPLINK URLs without exposing the configured API token."""

    API_URL = "https://vplink.in/api"

    def __init__(self, api_token: str, enabled: bool = False, timeout_seconds: float = 10.0) -> None:
        self.enabled = enabled
        self._api_token = api_token
        self._timeout = aiohttp.ClientTimeout(total=timeout_seconds)

    async def shorten(self, destination_url: str, alias: str | None = None) -> str:
        """Return the API's shortenedUrl, or raise a safe VplinkError."""
        if not destination_url or not destination_url.startswith(("https://", "http://")):
            raise VplinkError("The destination URL is invalid.")
        if not self._api_token:
            raise VplinkError("VPLINK is not configured.")

        params: dict[str, str] = {"api": self._api_token, "url": destination_url}
        if alias:
            params["alias"] = alias
        try:
            async with aiohttp.ClientSession(timeout=self._timeout) as session:
                async with session.get(self.API_URL, params=params) as response:
                    if response.status != 200:
                        logger.warning("VPLINK returned HTTP status %s", response.status)
                        raise VplinkError("VPLINK returned an unsuccessful HTTP response.")
                    payload: Any = await response.json(content_type=None)
        except VplinkError:
            raise
        except (aiohttp.ClientError, TimeoutError, ValueError):
            # Never include the request URL: it contains the secret token in its query string.
            logger.warning("VPLINK request failed due to a network or JSON error")
            raise VplinkError("VPLINK is temporarily unavailable.") from None

        if not isinstance(payload, dict) or payload.get("status") != "success":
            logger.warning("VPLINK returned an unsuccessful response status")
            raise VplinkError("VPLINK did not accept the destination URL.")
        shortened_url = payload.get("shortenedUrl")
        if not isinstance(shortened_url, str) or not shortened_url.startswith(("https://", "http://")):
            logger.warning("VPLINK success response did not contain a valid shortenedUrl")
            raise VplinkError("VPLINK returned an invalid shortened URL.")
        return shortened_url
