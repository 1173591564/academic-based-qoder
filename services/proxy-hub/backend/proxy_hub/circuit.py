"""Per-backend in-process circuit isolation for upstream Scholar calls."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from math import ceil
from threading import Lock


@dataclass
class CircuitState:
    """Mutable health state for one backend circuit."""

    failure_count: int = 0
    open_until: datetime | None = None
    recovery_probe_in_flight: bool = False


@dataclass(frozen=True)
class CircuitDecision:
    """Whether an upstream request may enter a backend circuit."""

    allowed: bool
    retry_after_seconds: int


class BackendCircuitBreaker:
    """Bounded failure circuit keyed by Scholar backend identifier."""

    def __init__(self, failure_threshold: int, recovery_seconds: int) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_seconds = recovery_seconds
        self._states: dict[str, CircuitState] = {}
        self._lock = Lock()

    def before_request(
        self,
        backend_id: str,
        *,
        at: datetime,
    ) -> CircuitDecision:
        """Permit closed circuits and one recovery probe for an open circuit."""
        with self._lock:
            state = self._states.get(backend_id)
            if state is None or state.open_until is None:
                return CircuitDecision(True, 0)
            if state.open_until > at:
                retry_after = max(
                    1,
                    ceil((state.open_until - at).total_seconds()),
                )
                return CircuitDecision(False, retry_after)
            if state.recovery_probe_in_flight:
                return CircuitDecision(False, 1)
            state.recovery_probe_in_flight = True
            return CircuitDecision(True, 0)

    def record_success(self, backend_id: str) -> None:
        """Close a circuit after an accepted upstream response."""
        with self._lock:
            self._states.pop(backend_id, None)

    def record_failure(self, backend_id: str, *, at: datetime) -> None:
        """Advance a circuit and open it at the configured threshold."""
        with self._lock:
            state = self._states.setdefault(backend_id, CircuitState())
            recovering = state.recovery_probe_in_flight
            state.recovery_probe_in_flight = False
            state.failure_count += 1
            if recovering or state.failure_count >= self.failure_threshold:
                state.open_until = at + timedelta(seconds=self.recovery_seconds)
