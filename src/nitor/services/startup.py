"""Reapplying saved lighting without a user interface.

This is what ``nitor --apply-saved`` runs, and what the ``systemd --user`` unit calls at login. It
must work with no display server at all.

Exit codes are chosen so that systemd reports the interesting failures and stays quiet about the
boring ones:

* ``0`` — lighting was applied, or there was nothing to do because no controller is connected
* ``1`` — a real failure: permissions, a backend error, a device that refuses to answer
* ``2`` — liquidctl is not installed
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from nitor.backend.base import AppliedLighting, HardwareBackend
from nitor.domain import Device, LightingState, NitorError
from nitor.services.settings import Settings

_LOGGER = logging.getLogger(__name__)

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_BACKEND_MISSING = 2


@dataclass(frozen=True, slots=True)
class ApplyOutcome:
    """What happened when the saved lighting was applied."""

    exit_code: int
    message: str
    applied: tuple[AppliedLighting, ...] = field(default=())

    @property
    def ok(self) -> bool:
        return self.exit_code == EXIT_OK


def select_device(devices: list[Device], selected_key: str | None) -> Device | None:
    """Pick the device to apply lighting to: the remembered one, else the only usable one."""
    usable = [
        device
        for device in devices
        if device.is_supported and device.profile is not None and device.profile.controllable
    ]
    if not usable:
        return None
    if selected_key:
        for device in usable:
            if device.key == selected_key:
                return device
    return usable[0]


def saved_state(settings: Settings, device: Device, devices: list[Device]) -> LightingState | None:
    """Find the lighting saved for a device.

    Device keys include the USB serial number when the hardware reports one, which is what makes
    settings survive ``/dev/hidrawN`` being renumbered. If the key does not match — a controller
    that stopped reporting a serial, say — a single saved profile is still used rather than
    ignoring the user's settings.
    """
    exact = settings.lighting_for(device.key)
    if exact is not None:
        return exact

    usable = [
        candidate
        for candidate in devices
        if candidate.is_supported
        and candidate.profile is not None
        and candidate.profile.controllable
    ]
    if len(usable) == 1 and len(settings.lighting) == 1:
        return next(iter(settings.lighting.values()))
    return None


def apply_saved(backend: HardwareBackend, settings: Settings) -> ApplyOutcome:
    """Apply the saved lighting once, and report what happened."""
    status = backend.status
    if not status.available:
        return ApplyOutcome(
            exit_code=EXIT_BACKEND_MISSING,
            message=status.summary or "The lighting backend is not installed.",
        )

    try:
        devices = backend.discover_devices()
    except NitorError as error:
        return ApplyOutcome(exit_code=EXIT_FAILED, message=error.message)

    device = select_device(devices, settings.selected_device)
    if device is None:
        return ApplyOutcome(
            exit_code=EXIT_OK,
            message="No supported NZXT controller is connected; nothing to apply.",
        )

    state = saved_state(settings, device, devices)
    if state is None:
        return ApplyOutcome(
            exit_code=EXIT_OK,
            message=f"No saved lighting for {device.display_name}; nothing to apply.",
        )

    try:
        initialized = backend.initialize_device(device)
        capabilities = initialized.capabilities
        if not capabilities.supports_lighting:
            return ApplyOutcome(
                exit_code=EXIT_OK,
                message=f"{initialized.display_name} has no controllable LED channels.",
            )
        normalized = state.normalized(capabilities)
        applied = backend.apply_lighting(initialized, normalized)
    except NitorError as error:
        _LOGGER.warning("could not apply saved lighting: %s", error.message)
        return ApplyOutcome(exit_code=EXIT_FAILED, message=error.message)

    _LOGGER.info("applied saved lighting to %s", initialized.display_name)
    return ApplyOutcome(
        exit_code=EXIT_OK,
        message=f"Applied {applied.effect} on {applied.channel} to {initialized.display_name}.",
        applied=(applied,),
    )


__all__ = [
    "EXIT_BACKEND_MISSING",
    "EXIT_FAILED",
    "EXIT_OK",
    "ApplyOutcome",
    "apply_saved",
    "saved_state",
    "select_device",
]
