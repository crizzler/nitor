"""Hardware backends.

``liquidctl_cli`` drives the real hardware; ``mock`` pretends to, so the interface and the tests do
not need a controller. ``commands`` holds the cooling safety boundary that every hardware command
passes through.
"""

from __future__ import annotations

from .base import AppliedLighting, BackendStatus, HardwareBackend
from .commands import build_set_argv, validate_argv
from .liquidctl_cli import LiquidctlBackend
from .mock import MockBackend, mock_devices
from .registry import (
    MODE_AUTO,
    MODE_LIQUIDCTL,
    MODE_MOCK,
    MODES,
    DeviceAccess,
    check_device_access,
    create_backend,
)

__all__ = [
    "MODES",
    "MODE_AUTO",
    "MODE_LIQUIDCTL",
    "MODE_MOCK",
    "AppliedLighting",
    "BackendStatus",
    "DeviceAccess",
    "HardwareBackend",
    "LiquidctlBackend",
    "MockBackend",
    "build_set_argv",
    "check_device_access",
    "create_backend",
    "mock_devices",
    "validate_argv",
]
