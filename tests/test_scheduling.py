"""Write scheduling: debouncing, coalescing, single-flight and rate limiting.

Tested with a fake clock rather than with sleeps, so the behaviour is exact and the suite stays
fast.
"""

from __future__ import annotations

import pytest

from nitor.domain import Color, LightingState
from nitor.services.scheduling import WriteScheduler


class FakeClock:
    """A clock the test moves by hand."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def scheduler(clock: FakeClock) -> WriteScheduler:
    return WriteScheduler(debounce=0.25, min_interval=0.5, clock=clock)


def state(color: str = "#00AAFF") -> LightingState:
    return LightingState(channel="led1", effect="fixed", colors=(Color.from_hex(color),))


def test_a_change_waits_for_the_debounce_to_elapse(
    scheduler: WriteScheduler, clock: FakeClock
) -> None:
    assert scheduler.submit("dev", state()) is not None
    assert scheduler.take() is None

    clock.advance(0.24)
    assert scheduler.take() is None

    clock.advance(0.02)
    write = scheduler.take()
    assert write is not None
    assert write.device_key == "dev"
    assert write.state == state()


def test_only_one_write_is_in_flight_at_a_time(scheduler: WriteScheduler, clock: FakeClock) -> None:
    scheduler.submit("dev", state())
    clock.advance(0.3)
    assert scheduler.take() is not None
    assert scheduler.in_flight_key == "dev"
    assert scheduler.take() is None


def test_dragging_through_colours_sends_only_the_final_one(
    scheduler: WriteScheduler, clock: FakeClock
) -> None:
    """The whole point of coalescing: a colour-wheel drag must not become fifty USB writes."""
    for step in range(50):
        scheduler.submit("dev", state(f"#{step:02X}0000"))
        clock.advance(0.01)  # faster than the debounce, as a real drag would be

    clock.advance(0.3)
    write = scheduler.take()
    assert write is not None
    assert write.state.colors[0].to_hex() == "#310000"
    assert scheduler.take() is None


def test_repeating_the_same_state_is_ignored(scheduler: WriteScheduler, clock: FakeClock) -> None:
    assert scheduler.submit("dev", state()) is not None
    assert scheduler.submit("dev", state()) is None

    clock.advance(0.3)
    first = scheduler.take()
    assert first is not None
    scheduler.complete(first.revision)

    # Re-applying the state that is already on the hardware would waste a USB transaction.
    assert scheduler.submit("dev", state()) is None


def test_forced_submission_is_always_sent(scheduler: WriteScheduler, clock: FakeClock) -> None:
    scheduler.submit("dev", state())
    clock.advance(0.3)
    write = scheduler.take()
    assert write is not None
    scheduler.complete(write.revision)

    assert scheduler.submit("dev", state(), force=True) is not None


def test_writes_are_spaced_out(scheduler: WriteScheduler, clock: FakeClock) -> None:
    scheduler.submit("dev", state("#00AAFF"))
    clock.advance(0.3)
    first = scheduler.take()
    assert first is not None
    scheduler.complete(first.revision)

    scheduler.submit("dev", state("#FF0000"))
    clock.advance(0.3)  # past the debounce, but not past the minimum interval
    assert scheduler.take() is None

    clock.advance(0.25)  # now 0.55s after the first write
    assert scheduler.take() is not None


def test_completed_writes_report_newer_work_waiting(
    scheduler: WriteScheduler, clock: FakeClock
) -> None:
    scheduler.submit("dev", state("#00AAFF"))
    clock.advance(0.3)
    first = scheduler.take()
    assert first is not None

    scheduler.submit("dev", state("#FF0000"), force=True)
    assert scheduler.complete(first.revision) is True


def test_a_failed_write_does_not_count_as_applied(
    scheduler: WriteScheduler, clock: FakeClock
) -> None:
    scheduler.submit("dev", state())
    clock.advance(0.3)
    write = scheduler.take()
    assert write is not None
    scheduler.apply_failed(write.revision)

    assert scheduler.applied_state == {}
    # ...so the same state is still worth sending, because it never reached the hardware.
    assert scheduler.submit("dev", state()) is not None


def test_applied_state_is_remembered_per_device(
    scheduler: WriteScheduler, clock: FakeClock
) -> None:
    scheduler.submit("dev-a", state())
    clock.advance(0.3)
    write = scheduler.take()
    assert write is not None
    scheduler.complete(write.revision)

    assert scheduler.applied_state == {"dev-a": state()}


def test_next_delay_describes_when_work_can_start(
    scheduler: WriteScheduler, clock: FakeClock
) -> None:
    assert scheduler.next_delay() is None

    scheduler.submit("dev", state())
    delay = scheduler.next_delay()
    assert delay is not None
    assert delay == pytest.approx(0.25)

    clock.advance(0.25)
    assert scheduler.next_delay() == pytest.approx(0.0)

    taken = scheduler.take()
    assert taken is not None
    assert scheduler.next_delay() is None


def test_cancelling_drops_pending_work(scheduler: WriteScheduler, clock: FakeClock) -> None:
    scheduler.submit("dev", state())
    assert scheduler.has_pending is True

    scheduler.cancel("dev")
    assert scheduler.has_pending is False

    scheduler.submit("dev", state())
    scheduler.cancel()
    assert scheduler.has_pending is False


def test_several_devices_are_served_in_submission_order(
    scheduler: WriteScheduler, clock: FakeClock
) -> None:
    scheduler.submit("dev-a", state("#00AAFF"))
    scheduler.submit("dev-b", state("#FF0000"))
    clock.advance(0.3)

    first = scheduler.take()
    assert first is not None
    assert first.device_key == "dev-a"
    scheduler.complete(first.revision)

    clock.advance(0.6)
    second = scheduler.take()
    assert second is not None
    assert second.device_key == "dev-b"


def test_zero_debounce_sends_immediately(clock: FakeClock) -> None:
    scheduler = WriteScheduler(debounce=0.0, min_interval=0.0, clock=clock)
    scheduler.submit("dev", state())
    assert scheduler.take() is not None
