"""Pure domain logic: colours, effects, devices, capabilities and errors.

Nothing in this package imports Qt or touches the system, which keeps it trivially testable.
"""

from __future__ import annotations

from .color import PRESETS, WHITE, Color, parse_color
from .effects import (
    DEFAULT_DIRECTION,
    DEFAULT_EFFECT,
    DEFAULT_SPEED,
    DIRECTIONS,
    EFFECTS_BY_FAMILY,
    FAMILY_HUE2,
    FAMILY_KRAKEN,
    OFF_EFFECT,
    SPEEDS,
    EffectSpec,
    ValidatedEffect,
    effects_for_family,
    get_effect,
    validate_request,
)
from .errors import (
    AutostartError,
    BackendMissingError,
    DeviceNotFoundError,
    EffectError,
    HardwareError,
    InvalidColorError,
    InvalidStateError,
    NitorError,
    NotSupportedError,
    PermissionDeniedError,
    SafetyViolationError,
)
from .models import (
    MAX_BRIGHTNESS,
    MIN_BRIGHTNESS,
    ChannelSpec,
    Device,
    DeviceCapabilities,
    DeviceDiscovery,
    DeviceProfile,
    LightingState,
    channel_label,
)
from .profiles import KNOWN_PROFILES, NZXT_VENDOR_ID, lookup_profile

__all__ = [
    "DEFAULT_DIRECTION",
    "DEFAULT_EFFECT",
    "DEFAULT_SPEED",
    "DIRECTIONS",
    "EFFECTS_BY_FAMILY",
    "FAMILY_HUE2",
    "FAMILY_KRAKEN",
    "KNOWN_PROFILES",
    "MAX_BRIGHTNESS",
    "MIN_BRIGHTNESS",
    "NZXT_VENDOR_ID",
    "OFF_EFFECT",
    "PRESETS",
    "SPEEDS",
    "WHITE",
    "AutostartError",
    "BackendMissingError",
    "ChannelSpec",
    "Color",
    "Device",
    "DeviceCapabilities",
    "DeviceDiscovery",
    "DeviceNotFoundError",
    "DeviceProfile",
    "EffectError",
    "EffectSpec",
    "HardwareError",
    "InvalidColorError",
    "InvalidStateError",
    "LightingState",
    "NitorError",
    "NotSupportedError",
    "PermissionDeniedError",
    "SafetyViolationError",
    "ValidatedEffect",
    "channel_label",
    "effects_for_family",
    "get_effect",
    "lookup_profile",
    "parse_color",
    "validate_request",
]
