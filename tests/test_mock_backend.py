"""The mock backend, which is what the interface is developed and demonstrated against."""

from __future__ import annotations

import time

import pytest

from nitor.backend.mock import MockBackend, mock_devices
from nitor.domain import (
    Color,
    EffectError,
    HardwareError,
    LightingState,
    PermissionDeniedError,
)


def test_mock_provides_the_two_target_devices() -> None:
    devices = mock_devices()
    assert [device.usb_id for device in devices] == ["1e71:2010", "1e71:3008"]
    assert all(device.is_supported for device in devices)
    assert devices[0].key != devices[1].key


def test_mock_is_recognisable_as_a_mock() -> None:
    backend = MockBackend()
    assert backend.is_mock is True
    assert backend.status.available is True
    assert "Mock" in backend.status.summary


def test_initialisation_reports_accessories_per_channel() -> None:
    backend = MockBackend()
    device = backend.initialize_device(backend.discover_devices()[0])
    channels = {channel.id: channel for channel in device.channels}
    assert channels["led1"].accessories == ("HUE 2 LED Strip 300 mm",)
    assert channels["led1"].led_count == 10
    assert channels["led2"].led_count == 16
    assert channels["sync"].led_count == 26


def test_initialisation_can_simulate_an_unplugged_channel() -> None:
    backend = MockBackend(empty_channels={"led2"})
    device = backend.initialize_device(backend.discover_devices()[0])
    channels = {channel.id: channel for channel in device.channels}
    assert channels["led2"].has_accessories is False
    assert channels["led2"].summary == "No accessories detected"


def test_kraken_mock_has_only_the_external_channel() -> None:
    backend = MockBackend()
    device = backend.initialize_device(backend.discover_devices()[1])
    assert [channel.id for channel in device.channels] == ["external"]


def test_applied_lighting_is_recorded_for_inspection() -> None:
    backend = MockBackend()
    device = backend.initialize_device(backend.discover_devices()[0])
    backend.apply_lighting(
        device,
        LightingState(channel="led1", effect="fixed", colors=(Color(0, 170, 255),)),
    )
    backend.turn_off(device, "led2")

    assert len(backend.applied) == 2
    assert backend.last_applied is not None
    assert backend.last_applied.is_off
    assert backend.applied[0].argv[-4:] == ("led1", "color", "fixed", "00aaff")


def test_the_mock_enforces_the_same_effect_limits_as_the_hardware() -> None:
    backend = MockBackend()
    kraken = backend.initialize_device(backend.discover_devices()[1])
    with pytest.raises(EffectError):
        # water-cooler needs two colours
        backend.apply_lighting(
            kraken,
            LightingState(channel="external", effect="water-cooler", colors=(Color(255, 0, 0),)),
        )
    assert backend.applied == ()


def test_queued_failures_surface_once_and_then_clear() -> None:
    backend = MockBackend()
    device = backend.initialize_device(backend.discover_devices()[0])
    backend.queue_failure(HardwareError("The controller did not respond in time."))

    state = LightingState(channel="led1", effect="fixed", colors=(Color(255, 255, 255),))
    with pytest.raises(HardwareError):
        backend.apply_lighting(device, state)
    backend.apply_lighting(device, state)
    assert len(backend.applied) == 1


def test_permission_denied_mode_reproduces_the_udev_problem() -> None:
    backend = MockBackend(permission_denied=True)
    device = backend.discover_devices()[0]
    with pytest.raises(PermissionDeniedError):
        backend.apply_lighting(
            device,
            LightingState(channel="led1", effect="fixed", colors=(Color(255, 255, 255),)),
        )
    backend.set_permission_denied(False)
    backend.apply_lighting(
        device,
        LightingState(channel="led1", effect="fixed", colors=(Color(255, 255, 255),)),
    )
    assert len(backend.applied) == 1


def test_latency_is_optional_and_configurable() -> None:
    backend = MockBackend(latency=0.05)
    started = time.monotonic()
    backend.discover_devices()
    assert time.monotonic() - started >= 0.05


def test_clear_resets_the_recorded_history() -> None:
    backend = MockBackend()
    device = backend.discover_devices()[0]
    backend.apply_lighting(
        device,
        LightingState(channel="led1", effect="fixed", colors=(Color(255, 255, 255),)),
    )
    backend.clear()
    assert backend.applied == ()
    assert backend.last_applied is None
