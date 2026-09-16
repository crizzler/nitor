"""A backend that pretends to be NZXT hardware.

This is what makes the interface developable and testable without a controller plugged in, and it
is what the test suite exercises. It implements the same contract as the real backend, records
every command it would have run, and can be told to fail on demand so the error paths can be seen
in the interface.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Iterable, Sequence
from typing import ClassVar

from nitor.domain import (
    Device,
    LightingState,
    NotSupportedError,
    PermissionDeniedError,
    channel_label,
)
from nitor.domain.models import ChannelSpec
from nitor.domain.profiles import lookup_profile

from .base import AppliedLighting, BackendStatus, HardwareBackend
from .commands import build_set_argv

_LOGGER = logging.getLogger(__name__)

NZXT_VENDOR_ID = 0x1E71


def mock_devices() -> list[Device]:
    """Two devices matching the models this project targets."""
    controller_profile = lookup_profile(NZXT_VENDOR_ID, 0x2010)
    kraken_profile = lookup_profile(NZXT_VENDOR_ID, 0x3008)
    return [
        Device(
            key="1e71:2010:MIT-0001",
            description="NZXT RGB & Fan Controller",
            vendor_id=NZXT_VENDOR_ID,
            product_id=0x2010,
            driver="SmartDevice2",
            bus="hid",
            address="/dev/hidraw5",
            serial="MIT-0001",
            profile=controller_profile,
        ),
        Device(
            key="1e71:3008:MIT-0002",
            description="NZXT Kraken Z (Z53, Z63 or Z73)",
            vendor_id=NZXT_VENDOR_ID,
            product_id=0x3008,
            driver="KrakenZ3",
            bus="hid",
            address="/dev/hidraw4",
            serial="MIT-0002",
            profile=kraken_profile,
        ),
    ]


class MockBackend(HardwareBackend):
    """An in-memory stand-in for the hardware backend."""

    name: ClassVar[str] = "mock"
    is_mock: ClassVar[bool] = True

    def __init__(
        self,
        *,
        devices: Sequence[Device] | None = None,
        latency: float = 0.0,
        empty_channels: Iterable[str] = (),
        permission_denied: bool = False,
        failures: Iterable[BaseException] = (),
    ) -> None:
        self._devices = list(devices) if devices is not None else mock_devices()
        self._latency = max(0.0, latency)
        self._empty_channels = set(empty_channels)
        self._permission_denied = permission_denied
        self._failures = list(failures)
        self._applied: list[AppliedLighting] = []
        self._lock = threading.Lock()

    # -- test and development helpers -----------------------------------------------------

    @property
    def applied(self) -> tuple[AppliedLighting, ...]:
        """Every command this backend was asked to run, newest last."""
        with self._lock:
            return tuple(self._applied)

    @property
    def last_applied(self) -> AppliedLighting | None:
        with self._lock:
            return self._applied[-1] if self._applied else None

    def queue_failure(self, error: BaseException) -> None:
        """Make the next hardware operation raise ``error``."""
        with self._lock:
            self._failures.append(error)

    def set_permission_denied(self, denied: bool) -> None:
        self._permission_denied = denied

    def clear(self) -> None:
        with self._lock:
            self._applied.clear()
            self._failures.clear()

    # -- backend contract -----------------------------------------------------------------

    @property
    def status(self) -> BackendStatus:
        return BackendStatus(
            name=self.name,
            available=True,
            version="mock",
            summary="Mock device (no hardware is touched)",
        )

    def discover_devices(self) -> list[Device]:
        self._sleep()
        return list(self._devices)

    def initialize_device(self, device: Device) -> Device:
        self._sleep()
        self._raise_if_denied()
        if device.profile is None:
            raise NotSupportedError(
                f"Nitor does not know how to control {device.display_name} yet."
            )
        return device.with_channels(self._channels_for(device), firmware="1.5.0")

    def apply_lighting(self, device: Device, state: LightingState) -> AppliedLighting:
        self._sleep()
        self._raise_if_denied()

        # The real backend refuses unsupported requests; the mock must behave the same way so the
        # interface cannot be developed against behaviour the hardware will not have.
        argv = build_set_argv(device, state)

        applied = AppliedLighting(
            device_key=device.key,
            channel=state.channel,
            effect=state.effect,
            colors=state.effective_colors(),
            speed=state.speed,
            direction=state.direction,
            argv=argv,
        )
        with self._lock:
            self._applied.append(applied)
        _LOGGER.debug("mock applied %s", applied)
        return applied

    # -- internals ------------------------------------------------------------------------

    def _channels_for(self, device: Device) -> tuple[ChannelSpec, ...]:
        profile = device.profile
        if profile is None:
            return ()

        accessories_by_channel = {
            "led1": ("HUE 2 LED Strip 300 mm",),
            "led2": ("AER RGB 2 140 mm", "AER RGB 2 140 mm"),
            "led3": ("HUE 2 Underglow 200 mm",),
            "external": ("HUE 2 LED Strip 300 mm",),
        }
        led_counts = {
            "led1": 10,
            "led2": 16,
            "led3": 6,
            "external": 10,
        }

        channels: list[ChannelSpec] = []
        for channel_id in profile.led_channels:
            if channel_id in self._empty_channels:
                accessories: tuple[str, ...] = ()
                led_count = 0
            else:
                accessories = accessories_by_channel.get(channel_id, ())
                led_count = led_counts.get(channel_id, 0)
            channels.append(
                ChannelSpec(
                    id=channel_id,
                    label=channel_label(channel_id),
                    accessories=accessories,
                    led_count=led_count,
                )
            )

        if profile.has_sync:
            channels.append(
                ChannelSpec(
                    id="sync",
                    label=channel_label("sync"),
                    led_count=sum(channel.led_count or 0 for channel in channels) or None,
                )
            )
        return tuple(channels)

    def _sleep(self) -> None:
        if self._latency:
            time.sleep(self._latency)

    def _raise_if_denied(self) -> None:
        if self._permission_denied:
            raise PermissionDeniedError(
                "The controller was found, but Linux denied access to it.",
                hint=(
                    "Install the liquidctl package, which provides the udev rule that grants "
                    "unprivileged access to supported controllers."
                ),
            )
        with self._lock:
            if self._failures:
                raise self._failures.pop(0)


__all__ = ["MockBackend", "mock_devices"]
