"""Deciding when to talk to the hardware.

The interface can change the requested lighting far faster than the controller should be written to:
dragging a colour wheel produces hundreds of states a second, and every write costs a liquidctl
subprocess launch plus a USB transaction.

This module owns that policy. It is deliberately free of Qt and of any hardware knowledge, so the
behaviour — debouncing, coalescing, single-flight and rate limiting — can be tested exactly with a
fake clock instead of by sleeping.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from nitor.domain import LightingState

#: How long the interface must be quiet before a change is sent.
DEFAULT_DEBOUNCE = 0.25

#: Minimum spacing between two hardware writes.
DEFAULT_MIN_INTERVAL = 0.5


@dataclass(frozen=True, slots=True)
class PendingWrite:
    """A lighting state that is ready to be sent."""

    device_key: str
    state: LightingState
    revision: int


@dataclass(slots=True)
class _Pending:
    device_key: str
    state: LightingState
    revision: int
    submitted_at: float


class WriteScheduler:
    """Coalesces UI changes into as few hardware writes as possible.

    Rules, in order of importance:

    * at most one write is in flight at a time (single-flight), because the controller is one device
    * newer state replaces older state that has not been sent yet (coalescing), so a drag ends up
      sending the final colour rather than every intermediate one
    * identical consecutive requests are dropped entirely
    * writes are spaced out by ``min_interval`` so the USB controller is never hammered
    """

    def __init__(
        self,
        *,
        debounce: float = DEFAULT_DEBOUNCE,
        min_interval: float = DEFAULT_MIN_INTERVAL,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._debounce = max(0.0, debounce)
        self._min_interval = max(0.0, min_interval)
        self._clock = clock
        self._lock = threading.Lock()
        self._pending: dict[str, _Pending] = {}
        self._in_flight: _Pending | None = None
        self._applied: dict[str, LightingState] = {}
        self._revision = 0
        self._last_write_at: float | None = None

    # -- submission -----------------------------------------------------------------------

    def submit(self, device_key: str, state: LightingState, *, force: bool = False) -> int | None:
        """Record a desired state, returning its revision or ``None`` if nothing needs sending."""
        with self._lock:
            if not force:
                in_flight = self._in_flight
                if (
                    in_flight is not None
                    and in_flight.device_key == device_key
                    and in_flight.state == state
                ):
                    # The very same state is already on its way to the hardware.
                    return None
                pending = self._pending.get(device_key)
                if pending is not None and pending.state == state:
                    return None
                if self._applied.get(device_key) == state and pending is None:
                    # Already applied and unchanged: do not touch the hardware again.
                    return None

            self._revision += 1
            self._pending[device_key] = _Pending(
                device_key=device_key,
                state=state,
                revision=self._revision,
                submitted_at=self._clock(),
            )
            return self._revision

    def cancel(self, device_key: str | None = None) -> None:
        """Drop pending work for one device, or for every device."""
        with self._lock:
            if device_key is None:
                self._pending.clear()
            else:
                self._pending.pop(device_key, None)

    # -- inspection -----------------------------------------------------------------------

    @property
    def has_pending(self) -> bool:
        with self._lock:
            return bool(self._pending)

    @property
    def in_flight_key(self) -> str | None:
        with self._lock:
            return self._in_flight.device_key if self._in_flight else None

    @property
    def applied_state(self) -> dict[str, LightingState]:
        """The last state successfully written, per device."""
        with self._lock:
            return dict(self._applied)

    def next_delay(self) -> float | None:
        """Seconds until :meth:`take` could return work, or ``None`` if it cannot."""
        with self._lock:
            if self._in_flight is not None or not self._pending:
                return None
            item = self._oldest_locked()
            ready_at = item.submitted_at + self._debounce
            if self._last_write_at is not None:
                ready_at = max(ready_at, self._last_write_at + self._min_interval)
            return max(0.0, ready_at - self._clock())

    # -- dispatch -------------------------------------------------------------------------

    def take(self) -> PendingWrite | None:
        """Return the next write when it is allowed to start, marking it in flight."""
        with self._lock:
            if self._in_flight is not None or not self._pending:
                return None

            item = self._oldest_locked()
            if self.next_delay_locked(item) > 0:
                return None

            del self._pending[item.device_key]
            self._in_flight = item
            return PendingWrite(
                device_key=item.device_key, state=item.state, revision=item.revision
            )

    def complete(self, revision: int, *, succeeded: bool = True) -> bool:
        """Mark a write finished. Returns whether newer work is already waiting."""
        with self._lock:
            in_flight = self._in_flight
            if in_flight is not None and in_flight.revision == revision:
                if succeeded:
                    self._applied[in_flight.device_key] = in_flight.state
                self._in_flight = None
            self._last_write_at = self._clock()
            return bool(self._pending)

    def apply_failed(self, revision: int) -> None:
        """Record a failed write without pretending the state reached the hardware."""
        self.complete(revision, succeeded=False)

    # -- internals ------------------------------------------------------------------------

    def _oldest_locked(self) -> _Pending:
        return min(self._pending.values(), key=lambda item: item.revision)

    def next_delay_locked(self, item: _Pending) -> float:
        ready_at = item.submitted_at + self._debounce
        if self._last_write_at is not None:
            ready_at = max(ready_at, self._last_write_at + self._min_interval)
        return max(0.0, ready_at - self._clock())


__all__ = [
    "DEFAULT_DEBOUNCE",
    "DEFAULT_MIN_INTERVAL",
    "PendingWrite",
    "WriteScheduler",
]
