"""Quota contract calculation tests."""

from datetime import datetime, timezone

import pytest

from proxy_hub.quota import quota_window_start, remaining_requests


def test_quota_window_start_uses_utc_epoch_boundaries() -> None:
    observed = datetime(2026, 9, 3, 1, 37, 42, tzinfo=timezone.utc)

    assert quota_window_start(observed, 3600) == datetime(
        2026,
        9,
        3,
        1,
        0,
        tzinfo=timezone.utc,
    )


def test_quota_calculations_reject_invalid_values() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        quota_window_start(datetime(2026, 9, 3), 60)
    with pytest.raises(ValueError, match="positive"):
        quota_window_start(datetime.now(timezone.utc), 0)
    with pytest.raises(ValueError, match="non-negative"):
        remaining_requests(10, -1)


def test_remaining_requests_never_becomes_negative() -> None:
    assert remaining_requests(10, 3) == 7
    assert remaining_requests(10, 12) == 0
