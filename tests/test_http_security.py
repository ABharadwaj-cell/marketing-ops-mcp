"""Regression checks for HTTP authentication before MCP dispatch."""

import pytest

from marketing_ops.server import BearerAuthASGI, run_http


@pytest.mark.asyncio
async def test_http_rejects_missing_and_invalid_tokens():
    calls = []
    events = []

    async def inner(scope, receive, send):
        calls.append(scope)
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    app = BearerAuthASGI(inner, "x" * 40)

    async def send(event):
        events.append(event)

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    for headers in ([], [(b"authorization", b"Bearer incorrect")]):
        events.clear()
        await app({"type": "http", "headers": headers}, receive, send)
        assert events[0]["status"] == 401
        assert not calls

    events.clear()
    await app(
        {"type": "http", "headers": [(b"authorization", b"Bearer " + b"x" * 40)]},
        receive,
        send,
    )
    assert events[0]["status"] == 200
    assert len(calls) == 1


def test_http_fails_closed_without_secret(monkeypatch):
    monkeypatch.delenv("MARKETING_OPS_HTTP_TOKEN", raising=False)
    with pytest.raises(ValueError, match="HTTP is disabled"):
        run_http(None)


def test_http_rejects_weak_secret():
    with pytest.raises(ValueError, match="at least 32"):
        BearerAuthASGI(None, "short")


@pytest.mark.asyncio
async def test_http_rejects_duplicate_authorization_headers():
    calls = []
    events = []

    async def inner(scope, receive, send):
        calls.append(scope)

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(event):
        events.append(event)

    valid = b"Bearer " + b"x" * 40
    app = BearerAuthASGI(inner, "x" * 40)
    for headers in (
        [(b"authorization", valid), (b"authorization", b"Bearer invalid")],
        [(b"Authorization", valid), (b"AUTHORIZATION", valid)],
    ):
        events.clear()
        await app({"type": "http", "headers": headers}, receive, send)
        assert events[0]["status"] == 401
        assert not calls


@pytest.mark.asyncio
async def test_websocket_upgrade_is_not_forwarded():
    calls = []
    events = []

    async def inner(scope, receive, send):
        calls.append(scope)

    async def receive():
        return {"type": "websocket.connect"}

    async def send(event):
        events.append(event)

    app = BearerAuthASGI(inner, "x" * 40)
    await app({"type": "websocket", "headers": []}, receive, send)
    assert events == [{"type": "websocket.close", "code": 1008}]
    assert not calls
