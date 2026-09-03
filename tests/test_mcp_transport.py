"""Transport configuration tests for the Scholar MCP process."""

import pytest

from scholar_mcp.transport import TransportSettings, is_loopback_host


@pytest.mark.parametrize("host", ["127.0.0.1", "::1"])
def test_numeric_loopback_hosts_are_accepted(host):
    assert is_loopback_host(host)


@pytest.mark.parametrize("host", ["localhost", "0.0.0.0", "scholar.internal"])
def test_non_numeric_or_non_loopback_hosts_are_rejected(host):
    assert not is_loopback_host(host)


def test_stdio_needs_no_network_credential():
    TransportSettings(
        transport="stdio",
        host="0.0.0.0",
        port=8000,
        bearer_token="",
        allow_insecure_loopback=False,
    ).validate()


def test_authenticated_http_accepts_non_loopback_host():
    TransportSettings(
        transport="streamable-http",
        host="0.0.0.0",
        port=8000,
        bearer_token="service-secret",
        allow_insecure_loopback=False,
    ).validate()


def test_unauthenticated_http_is_limited_to_explicit_loopback():
    TransportSettings(
        transport="streamable-http",
        host="127.0.0.1",
        port=8000,
        bearer_token="",
        allow_insecure_loopback=True,
    ).validate()

    with pytest.raises(RuntimeError, match="required for streamable HTTP"):
        TransportSettings(
            transport="streamable-http",
            host="0.0.0.0",
            port=8000,
            bearer_token="",
            allow_insecure_loopback=True,
        ).validate()


def test_unknown_transport_is_rejected():
    with pytest.raises(RuntimeError, match="must be stdio or streamable-http"):
        TransportSettings(
            transport="websocket",
            host="127.0.0.1",
            port=8000,
            bearer_token="",
            allow_insecure_loopback=False,
        ).validate()
