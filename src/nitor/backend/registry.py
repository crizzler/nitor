"""Choosing a backend and checking whether it can actually be used."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Final

from nitor.domain import Device

from .base import BackendStatus, HardwareBackend
from .liquidctl_cli import LiquidctlBackend
from .mock import MockBackend

MODE_AUTO: Final = "auto"
MODE_LIQUIDCTL: Final = "liquidctl"
MODE_MOCK: Final = "mock"
MODES: Final[tuple[str, ...]] = (MODE_AUTO, MODE_LIQUIDCTL, MODE_MOCK)


@dataclass(frozen=True, slots=True)
class DeviceAccess:
    """Whether a device can actually be written to by this user."""

    device_key: str
    accessible: bool
    reason: str = ""


def create_backend(
    mode: str = MODE_AUTO, *, mock_options: dict[str, object] | None = None
) -> HardwareBackend:
    """Build the backend for ``mode``.

    ``auto`` returns the real backend even when liquidctl is missing, so that the interface can
    explain what to install rather than silently pretending success.
    """
    if mode == MODE_MOCK:
        return MockBackend(**(mock_options or {}))
    if mode in (MODE_AUTO, MODE_LIQUIDCTL):
        return LiquidctlBackend()
    raise ValueError(f"Unknown backend mode '{mode}'. Expected one of: {', '.join(MODES)}.")


def backend_status(backend: HardwareBackend) -> BackendStatus:
    """Availability of a backend, with a mock-friendly message."""
    return backend.status


def check_device_access(backend: HardwareBackend, devices: list[Device]) -> dict[str, DeviceAccess]:
    """Report which devices this user may write to.

    A mock backend is always accessible. For real devices the check is a read/write test on the
    hidraw node liquidctl reported, which distinguishes "nothing is plugged in" from "plugged in
    but not permitted" — two situations that need completely different advice.
    """
    access: dict[str, DeviceAccess] = {}
    for device in devices:
        if backend.is_mock:
            access[device.key] = DeviceAccess(device_key=device.key, accessible=True)
            continue
        if not device.address:
            access[device.key] = DeviceAccess(
                device_key=device.key,
                accessible=False,
                reason="The backend did not report a device path to check.",
            )
            continue
        writable = os.access(device.address, os.R_OK | os.W_OK)
        access[device.key] = DeviceAccess(
            device_key=device.key,
            accessible=writable,
            reason="" if writable else f"{device.address} is not writable by this user",
        )
    return access


def all_accessible(access: dict[str, DeviceAccess]) -> bool:
    return all(entry.accessible for entry in access.values())


__all__ = [
    "MODES",
    "MODE_AUTO",
    "MODE_LIQUIDCTL",
    "MODE_MOCK",
    "DeviceAccess",
    "all_accessible",
    "backend_status",
    "check_device_access",
    "create_backend",
]
