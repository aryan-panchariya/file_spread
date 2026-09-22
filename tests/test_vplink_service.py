from __future__ import annotations

import pytest

from app.services.vplink_service import VplinkError, VplinkService


class FakeResponse:
    def __init__(self, status: int, payload):
        self.status = status
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def json(self, content_type=None):
        return self._payload


class FakeSession:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def get(self, url, params):
        self.url = url
        self.params = params
        return self.response


@pytest.mark.asyncio
async def test_successful_vplink_response(monkeypatch):
    response = FakeResponse(200, {"status": "success", "shortenedUrl": "https://vplink.in/abc"})
    session = FakeSession(response)

    class FakeClientSession:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return session

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("app.services.vplink_service.aiohttp.ClientSession", FakeClientSession)

    service = VplinkService("secret-token", enabled=True)
    assert await service.shorten("https://t.me/example?start=file_abc") == "https://vplink.in/abc"
    assert session.params["api"] == "secret-token"


@pytest.mark.asyncio
async def test_unsuccessful_vplink_response(monkeypatch):
    response = FakeResponse(200, {"status": "error"})
    session = FakeSession(response)

    class FakeClientSession:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return session

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("app.services.vplink_service.aiohttp.ClientSession", FakeClientSession)

    with pytest.raises(VplinkError):
        await VplinkService("secret-token", enabled=True).shorten("https://example.com")


@pytest.mark.asyncio
async def test_missing_shortened_url(monkeypatch):
    response = FakeResponse(200, {"status": "success"})
    session = FakeSession(response)

    class FakeClientSession:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return session

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("app.services.vplink_service.aiohttp.ClientSession", FakeClientSession)

    with pytest.raises(VplinkError):
        await VplinkService("secret-token", enabled=True).shorten("https://example.com")
