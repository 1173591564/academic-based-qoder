"""Safe retry and backend circuit isolation tests."""

import asyncio
from datetime import timedelta

import httpx
import pytest

from proxy_hub.circuit import BackendCircuitBreaker
from proxy_hub.config import Settings
from proxy_hub.mcp_gateway import CircuitOpenError, send_upstream
from proxy_hub.models import utc_now


def test_circuit_opens_and_allows_one_recovery_probe() -> None:
    breaker = BackendCircuitBreaker(failure_threshold=2, recovery_seconds=30)
    now = utc_now()

    breaker.record_failure("backend", at=now)
    assert breaker.before_request("backend", at=now).allowed
    breaker.record_failure("backend", at=now)
    denied = breaker.before_request("backend", at=now)
    recovery = breaker.before_request(
        "backend",
        at=now + timedelta(seconds=31),
    )
    concurrent_recovery = breaker.before_request(
        "backend",
        at=now + timedelta(seconds=31),
    )

    assert not denied.allowed
    assert denied.retry_after_seconds == 30
    assert recovery.allowed
    assert not concurrent_recovery.allowed
    breaker.record_success("backend")
    assert breaker.before_request("backend", at=now).allowed


def test_get_retries_but_post_never_retries() -> None:
    get_attempts = 0

    def get_handler(_request: httpx.Request) -> httpx.Response:
        nonlocal get_attempts
        get_attempts += 1
        return httpx.Response(503 if get_attempts == 1 else 200)

    async def run_get() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(get_handler)
        ) as client:
            return await send_upstream(
                client,
                BackendCircuitBreaker(3, 30),
                Settings(
                    environment="test",
                    backend_retry_backoff_seconds=0,
                ),
                backend_id="backend",
                method="GET",
                backend_url="https://scholar.test/mcp",
                headers={},
                body=b"",
            )

    response = asyncio.run(run_get())
    assert response.status_code == 200
    assert get_attempts == 2

    post_attempts = 0

    def post_handler(_request: httpx.Request) -> httpx.Response:
        nonlocal post_attempts
        post_attempts += 1
        raise httpx.ConnectError("unavailable")

    async def run_post() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(post_handler)
        ) as client:
            await send_upstream(
                client,
                BackendCircuitBreaker(1, 30),
                Settings(
                    environment="test",
                    backend_retry_backoff_seconds=0,
                ),
                backend_id="backend",
                method="POST",
                backend_url="https://scholar.test/mcp",
                headers={},
                body=b"{}",
            )

    with pytest.raises(httpx.ConnectError):
        asyncio.run(run_post())
    assert post_attempts == 1


def test_open_circuit_rejects_without_sending() -> None:
    breaker = BackendCircuitBreaker(failure_threshold=1, recovery_seconds=30)
    breaker.record_failure("backend", at=utc_now())
    attempts = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(200)

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await send_upstream(
                client,
                breaker,
                Settings(environment="test"),
                backend_id="backend",
                method="GET",
                backend_url="https://scholar.test/mcp",
                headers={},
                body=b"",
            )

    with pytest.raises(CircuitOpenError):
        asyncio.run(run())
    assert attempts == 0
